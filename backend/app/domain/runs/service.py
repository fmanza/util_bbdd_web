"""Ejecuciones: encolar, consultar, cancelar, relanzar, purgar y retención (ADR-002, ADR-005).

La API solo encola (fila ``runs`` en ``queued``); el worker la reclama y la ejecuta en un subproceso.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Final

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.ulid import new_ulid
from app.db.models import TERMINAL_STATUSES, Artifact, Project, ProjectMember, ProjectRole, Run, User, utcnow
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.projects.errors import ProjectForbiddenError
from app.domain.projects.service import Membership, get_membership, get_project_connection
from app.domain.runs.errors import (
    ArtifactNotFoundError,
    QuotaExceededError,
    RunNotFoundError,
    RunParamsError,
    RunStateError,
    TooManyRunsError,
)
from app.domain.runs.operations import get_operation, validate_params
from app.domain.storage.settings import effective_settings, quota_bytes
from app.domain.templates.service import check_run_templates
from app.workspace.layout import UnsafePathError, remove_tree, run_dir, run_relative_path, safe_path

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ("queued", "running")
#: Diario de constraints que deja un volcado interrumpido (util_bbdd 4.4.0, G31) y destino del volcado (conexión y
#: alias), en ``work/`` del run: no son artefactos. Mientras exista el diario, las constraints siguen desactivadas.
DUMP_JOURNAL_PATH: Final = "work/constraints_journal.json"
DUMP_TARGET_PATH: Final = "work/target.json"


def dump_journal(run: Run, settings: Settings) -> Path | None:
    """Diario de constraints pendiente de un ``dump_apply`` terminado (``None`` si no queda ninguno)."""
    if run.operation != "dump_apply" or not run.workspace_path or run.status not in TERMINAL_STATUSES:
        return None
    path = run_dir(settings.workspace_dir, run.workspace_path) / DUMP_JOURNAL_PATH
    return path if path.is_file() else None


@dataclass(frozen=True)
class RunAccess:
    """Ejecución visible y el rol del usuario en su proyecto."""

    run: Run
    membership: Membership


@dataclass(frozen=True)
class RunFilters:
    status: str | None = None
    operation: str | None = None
    user_id: int | None = None
    q: str | None = None


# --- consultas ---------------------------------------------------------------------------------------------------


def _filtered(query: Any, filters: RunFilters) -> Any:
    if filters.status:
        query = query.where(Run.status == filters.status)
    if filters.operation:
        query = query.where(Run.operation == filters.operation)
    if filters.user_id is not None:
        query = query.where(Run.user_id == filters.user_id)
    if filters.q:
        pattern = f"%{filters.q.strip().lower()}%"
        query = query.join(User, User.id == Run.user_id, isouter=True).where(
            or_(
                func.lower(Run.id).like(pattern),
                func.lower(Run.operation).like(pattern),
                func.lower(User.username).like(pattern),
                func.lower(func.coalesce(Run.progress_message, "")).like(pattern),
            )
        )
    return query


def list_project_runs(
    db: Session, project: Project, filters: RunFilters, *, limit: int, offset: int
) -> tuple[list[Run], int]:
    """Historial del proyecto, más recientes primero (agrupado por ejecución: una fila por run)."""
    query = _filtered(select(Run).where(Run.project_id == project.id), filters)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(Run.created_at.desc(), Run.id.desc()).limit(limit).offset(offset)).unique().all()
    return list(rows), total


def list_user_runs(db: Session, user: User, filters: RunFilters, *, limit: int, offset: int) -> tuple[list[Run], int]:
    """Ejecuciones recientes de todos los proyectos de los que ``user`` es miembro."""
    projects = select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)
    query = _filtered(select(Run).where(Run.project_id.in_(projects)), filters)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(Run.created_at.desc(), Run.id.desc()).limit(limit).offset(offset)).unique().all()
    return list(rows), total


def get_access(db: Session, user: User, run_id: str, minimum: ProjectRole = "viewer") -> RunAccess:
    """Ejecución visible para ``user`` con su rol.

    Raises:
        RunNotFoundError: No existe o no es miembro del proyecto.
        ProjectForbiddenError: Su rol no llega a ``minimum``.
    """
    run = db.get(Run, run_id)
    if run is None:
        raise RunNotFoundError()
    try:
        membership = get_membership(db, user, run.project_id)
    except Exception as exc:
        if isinstance(exc, ProjectForbiddenError):
            raise
        raise RunNotFoundError() from None
    if not membership.can(minimum):
        raise ProjectForbiddenError()
    return RunAccess(run=run, membership=membership)


def artifact_count(db: Session, run_ids: list[str]) -> dict[str, int]:
    if not run_ids:
        return {}
    rows = db.execute(
        select(Artifact.run_id, func.count()).where(Artifact.run_id.in_(run_ids)).group_by(Artifact.run_id)
    ).all()
    return {str(run_id): int(count) for run_id, count in rows}


def get_artifact(db: Session, run: Run, artifact_id: int, settings: Settings) -> tuple[Artifact, Path]:
    """Artefacto del run y su ruta absoluta comprobada.

    Raises:
        ArtifactNotFoundError: No existe, el run está purgado o la ruta guardada sale de la carpeta del run.
    """
    artifact = db.scalar(select(Artifact).where(Artifact.id == artifact_id, Artifact.run_id == run.id))
    return _checked(run, artifact, settings)


def get_artifact_by_path(db: Session, run: Run, path: str, settings: Settings) -> tuple[Artifact, Path]:
    """Como :func:`get_artifact`, pero por ruta: solo sirve ficheros **registrados** del run (sitio HTML).

    Raises:
        ArtifactNotFoundError: La ruta no es un artefacto del run o no está en disco.
    """
    artifact = db.scalar(select(Artifact).where(Artifact.run_id == run.id, Artifact.path == path))
    return _checked(run, artifact, settings)


def _checked(run: Run, artifact: Artifact | None, settings: Settings) -> tuple[Artifact, Path]:
    if artifact is None or run.workspace_path is None:
        raise ArtifactNotFoundError()
    try:
        path = safe_path(run_dir(settings.workspace_dir, run.workspace_path), artifact.path)
    except UnsafePathError:
        logger.warning("Ruta de artefacto fuera del run", extra={"run_id": run.id, "artifact_id": artifact.id})
        raise ArtifactNotFoundError() from None
    if not path.is_file():
        raise ArtifactNotFoundError()
    return artifact, path


# --- encolar -----------------------------------------------------------------------------------------------------


def usage_bytes(db: Session, user_id: int) -> int:
    """Espacio que usa ``user_id``: sus ejecuciones no purgadas y sus ficheros subidos (Fase 9)."""
    from app.domain.uploads.service import uploads_bytes

    runs = db.scalar(
        select(func.coalesce(func.sum(Run.size_bytes), 0)).where(Run.user_id == user_id, Run.status != "purged")
    )
    return int(runs or 0) + uploads_bytes(db, user_id)


def _check_quota(db: Session, user: User, settings: Settings, ctx: RequestContext) -> None:
    """Cuota efectiva del usuario (ADR-012); con la purga por cuota activa, antes de rechazar se intenta liberar.

    Raises:
        QuotaExceededError: Sigue sin sitio.
    """
    from app.domain.storage.purge import purge_for_quota  # importa este módulo: aquí para evitar el ciclo

    effective = effective_settings(db, settings)
    quota = quota_bytes(user, effective)
    if quota is None or usage_bytes(db, user.id) < quota:
        return
    purge_for_quota(db, user, effective, ctx=ctx)
    if usage_bytes(db, user.id) >= quota:
        raise QuotaExceededError("Purga ejecuciones antiguas para liberar espacio.")


def enqueue(
    db: Session,
    user: User,
    membership: Membership,
    *,
    operation: str,
    params: dict[str, Any],
    settings: Settings,
    ctx: RequestContext,
    relaunched_from: str | None = None,
) -> Run:
    """Valida y encola una ejecución.

    Raises:
        ProjectForbiddenError: Rol inferior a ``editor``.
        UnknownOperationError, RunParamsError: Operación o parámetros no válidos (422).
        TooManyRunsError: El usuario ya tiene ``max_queued_per_user`` en cola o en curso (429).
        QuotaExceededError: El usuario supera su cuota (409), aun con la purga por cuota si está activa.
        MigrationForbiddenError, DumpForbiddenError, RunStateError: Reglas de escritura en la BD destino
            (``migrations.check_apply``, ADR-008; ``dumps.check_apply`` y ``dumps.check_restore``, ADR-009).
    """
    from app.domain.runs import bulks, dumps, migrations  # importan este módulo: aquí para evitar el ciclo

    if not membership.can("editor"):
        raise ProjectForbiddenError()
    spec = get_operation(operation)
    clean = validate_params(spec, params)
    for alias in spec.connection_params(clean):
        try:
            get_project_connection(db, membership.project, alias)
        except Exception:
            raise RunParamsError(
                f"El proyecto no tiene ninguna conexión con el alias «{alias}».",
                errors=[{"loc": ["body", "params"], "msg": f"Alias desconocido: {alias}", "type": "value_error"}],
            ) from None
    if spec.name == "migrate_plan":
        migrations.check_plan(db, membership, clean)
    elif spec.name == "migrate_apply":
        migrations.check_apply(db, user, membership, clean, settings)
    elif spec.name == "dump_apply":
        dumps.check_apply(db, user, membership, clean, settings)
    elif spec.name == "dump_restore":
        dumps.check_restore(db, user, membership, clean, settings)
    elif spec.name == "bulk_preview":
        bulks.check_preview(db, membership, clean)
    elif spec.name == "bulk_apply":
        bulks.check_apply(db, user, membership, clean, settings)
    elif spec.name == "documentation":
        check_run_templates(db, membership.project, clean)
    active = db.scalar(select(func.count()).where(Run.user_id == user.id, Run.status.in_(ACTIVE_STATUSES))) or 0
    if active >= settings.max_queued_per_user:
        raise TooManyRunsError(f"Tienes {active} ejecuciones en cola o en curso; espera a que terminen.")
    _check_quota(db, user, settings, ctx)
    now = utcnow()
    run_id = new_ulid()
    project = membership.project
    run = Run(
        id=run_id,
        project_id=project.id,
        user_id=user.id,
        operation=spec.name,
        params=clean,
        status="queued",
        phase="queued",
        created_at=now,
        workspace_path=run_relative_path(project.owner_id, project.id, now, spec.name, run_id),
        relaunched_from=relaunched_from,
    )
    db.add(run)
    audit.record(
        db, action=AuditAction.RUN_CREATE, ctx=ctx, actor_id=user.id, target_type="run", target_id=run_id,
        details={
            "project_id": project.id, "operation": spec.name, "relaunched_from": relaunched_from,
            **({"migration": {k: clean.get(k) for k in ("mode", "plan_run", "target_connection", "dry_run_run")}}
               if spec.name == "migrate_apply" else {}),
            **({"dump": _dump_audit(db, clean)} if spec.name == "dump_apply" else {}),
            **({"dump_restore": {"dump_run": clean["dump_run"], "target_connection": clean["confirm"]}}
               if spec.name == "dump_restore" else {}),
            **({"bulk": _bulk_audit(db, clean)} if spec.name == "bulk_apply" else {}),
        },
    )  # fmt: skip
    db.commit()
    return run


def _dump_audit(db: Session, params: dict[str, Any]) -> dict[str, Any]:
    """Qué y dónde escribe un volcado, para ``audit_log`` (los parámetros viven en su vista previa)."""
    preview = db.get(Run, params["preview_run"])
    shown = ("source_connection", "target_connection", "tables", "truncate_target", "on_error")
    return {"preview_run": params["preview_run"], **{k: preview.params.get(k) for k in shown if preview}}


def _bulk_audit(db: Session, params: dict[str, Any]) -> dict[str, Any]:
    """Qué fichero, dónde y cómo escribe una carga, para ``audit_log`` (los parámetros viven en su vista previa)."""
    preview = db.get(Run, params["preview_run"])
    shown = ("upload", "target_connection", "table", "operation", "on_error", "parallel")
    return {
        "preview_run": params["preview_run"],
        "confirm_rows": params.get("confirm_rows"),
        **{k: preview.params.get(k) for k in shown if preview},
    }


def relaunch(db: Session, user: User, access: RunAccess, *, settings: Settings, ctx: RequestContext) -> Run:
    """Nueva ejecución con la misma operación y parámetros.

    Raises:
        RunStateError: La operación no se relanza (``form=False``, p. ej. ``migrate_apply``: exige un modo seco nuevo).
    """
    run = access.run
    if not get_operation(run.operation).form:
        raise RunStateError("Esta ejecución no se puede relanzar: lánzala de nuevo desde su origen.")
    return enqueue(
        db, user, access.membership, operation=run.operation, params=dict(run.params), settings=settings, ctx=ctx,
        relaunched_from=run.id,
    )  # fmt: skip


def cancel(db: Session, user: User, access: RunAccess, *, ctx: RequestContext) -> Run:
    """Cancela: una en cola pasa a ``cancelled`` al momento; una en curso la para util_bbdd o la termina el worker.

    Las escrituras en una BD destino (``migrate_apply``, ``dump_apply`` y ``bulk_apply``, desde las 1.3.0, 1.4.0 y
    1.5.0) paran solo entre sentencias o entre lotes; el worker no las termina al cancelar (ADR-008, ADR-009, ADR-010).

    Raises:
        ProjectForbiddenError: Rol inferior a ``editor``.
        RunStateError: Ya terminó.
    """
    if not access.membership.can("editor"):
        raise ProjectForbiddenError()
    run = access.run
    now = utcnow()
    result = db.execute(
        update(Run)
        .where(Run.id == run.id, Run.status == "queued")
        .values(status="cancelled", phase="done", finished_at=now, error_code="cancelled")
    )
    if not getattr(result, "rowcount", 0):
        result = db.execute(update(Run).where(Run.id == run.id, Run.status == "running").values(cancel_requested=True))
        if not getattr(result, "rowcount", 0):
            db.rollback()
            raise RunStateError("La ejecución ya ha terminado.")
    audit.record(db, action=AuditAction.RUN_CANCEL, ctx=ctx, actor_id=user.id, target_type="run", target_id=run.id)
    db.commit()
    db.refresh(run)
    return run


def purge_run(db: Session, run: Run, settings: Settings) -> None:
    """Borra la carpeta y los artefactos de un run terminado; conserva la fila y su ``manifest`` (``purged``)."""
    if run.workspace_path:
        try:
            remove_tree(run_dir(settings.workspace_dir, run.workspace_path))
        except UnsafePathError:
            logger.warning("Ruta de run fuera del workspace", extra={"run_id": run.id})
    for artifact in run.artifacts:
        db.delete(artifact)
    run.status = "purged"
    run.size_bytes = 0


def purge(db: Session, user: User, access: RunAccess, *, settings: Settings, ctx: RequestContext) -> None:
    """Purga a petición de un editor.

    Raises:
        ProjectForbiddenError, RunStateError: No es editor o la ejecución no ha terminado.
    """
    if not access.membership.can("editor"):
        raise ProjectForbiddenError()
    if access.run.status not in TERMINAL_STATUSES:
        raise RunStateError("Solo se purgan ejecuciones terminadas.")
    if dump_journal(access.run, settings) is not None:
        raise RunStateError("Este volcado dejó constraints sin restaurar en el destino: restáuralas antes de purgarlo.")
    purge_run(db, access.run, settings)
    audit.record(
        db, action=AuditAction.RUN_PURGE, ctx=ctx, actor_id=user.id, target_type="run", target_id=access.run.id
    )
    db.commit()


# --- retención ---------------------------------------------------------------------------------------------------


def retention_candidates(db: Session, settings: Settings, *, now: datetime | None = None) -> list[Run]:
    """Runs terminados que la retención debe purgar: más antiguos que ``run_retention_days`` o fuera de los
    ``run_retention_per_project`` más recientes de su proyecto."""
    now = now or utcnow()
    selected: dict[str, Run] = {}
    terminal = select(Run).where(Run.status.in_(tuple(TERMINAL_STATUSES)))
    if settings.run_retention_days:
        cutoff = now - timedelta(days=settings.run_retention_days)
        for run in db.scalars(terminal.where(Run.finished_at < cutoff)).unique().all():
            selected[run.id] = run
    if settings.run_retention_per_project:
        keep = settings.run_retention_per_project
        ranked = (
            select(
                Run.id, func.row_number().over(partition_by=Run.project_id, order_by=Run.created_at.desc()).label("rn")
            )
            .where(Run.status != "purged")
            .subquery()
        )
        old_ids = select(ranked.c.id).where(ranked.c.rn > keep)
        for run in db.scalars(terminal.where(Run.id.in_(old_ids))).unique().all():
            selected[run.id] = run
    # Un volcado con constraints sin restaurar conserva su diario (G31): no se purga hasta restaurarlas.
    return [run for run in selected.values() if dump_journal(run, settings) is None]


def apply_retention(db: Session, settings: Settings, *, now: datetime | None = None) -> int:
    """Purga los candidatos de retención; devuelve cuántos."""
    candidates = retention_candidates(db, settings, now=now)
    for run in candidates:
        purge_run(db, run, settings)
    db.commit()
    if candidates:
        logger.info("Retención aplicada", extra={"purged": len(candidates)})
    return len(candidates)
