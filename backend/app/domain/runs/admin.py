"""Ejecuciones desde administración: lista de todos los proyectos y borrado completo (fila y ficheros).

Un administrador que no es miembro de un proyecto no ve su contenido (404 en el resto de la API). Aquí solo ve
metadatos (proyecto, operación, usuario, estado, tamaño y fechas), nunca ``params``, mensajes ni artefactos, y puede
**borrar** ejecuciones terminadas: a diferencia de la purga (que deja la fila ``purged``), desaparecen del historial.
La auditoría conserva el resumen. Sesión ``2026-11-06-explorer-runs-lists`` (D1-D3, D8).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Final, Literal

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import TERMINAL_STATUSES, Artifact, Project, Run, User
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.projects.errors import ProjectNotFoundError
from app.domain.runs.errors import RunNotFoundError, RunStateError
from app.domain.runs.service import artifact_count, dump_journal
from app.domain.sorting import SortOrder, like_pattern, order_by
from app.workspace.layout import UnsafePathError, remove_tree, run_dir

logger = logging.getLogger(__name__)

#: Estados que se pueden borrar: terminadas y purgadas (las activas se cancelan antes).
DELETABLE: Final = frozenset({*TERMINAL_STATUSES, "purged"})
AdminRunSort = Literal["created_at", "finished_at", "project", "operation", "status", "user", "size"]


class DeleteConfirmationError(AppError):
    status = 422
    title = "Confirmación incorrecta: escribe el nombre exacto del proyecto"


@dataclass(frozen=True)
class AdminRun:
    id: str
    project_id: int
    project_name: str
    operation: str
    status: str
    username: str | None
    created_at: Any
    finished_at: Any
    size_bytes: int
    artifacts_count: int


@dataclass(frozen=True)
class ProjectRunsDeletion:
    deleted: int
    skipped_active: int
    skipped_pending_dump: int
    freed_bytes: int


_SORT: Final[dict[str, Any]] = {
    "created_at": Run.created_at,
    "finished_at": Run.finished_at,
    "project": func.lower(Project.name),
    "operation": Run.operation,
    "status": Run.status,
    "user": func.lower(func.coalesce(User.username, "")),
    "size": Run.size_bytes,
}


def list_all_runs(
    db: Session,
    *,
    q: str | None,
    project_id: int | None,
    status: str | None,
    sort: AdminRunSort | None,
    order: SortOrder | None,
    limit: int,
    offset: int,
) -> tuple[list[AdminRun], int]:
    """Ejecuciones de todos los proyectos (más recientes primero por defecto)."""
    query = (
        select(Run.id, Run.project_id, Project.name, Run.operation, Run.status, User.username, Run.created_at,
               Run.finished_at, Run.size_bytes)
        .join(Project, Project.id == Run.project_id)
        .join(User, User.id == Run.user_id, isouter=True)
    )  # fmt: skip
    if project_id is not None:
        query = query.where(Run.project_id == project_id)
    if status:
        query = query.where(Run.status == status)
    if q and q.strip():
        pattern = like_pattern(q)
        query = query.where(
            or_(
                func.lower(Run.id).like(pattern, escape="\\"),
                func.lower(Run.operation).like(pattern, escape="\\"),
                func.lower(func.coalesce(User.username, "")).like(pattern, escape="\\"),
                func.lower(Project.name).like(pattern, escape="\\"),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    clauses = order_by(_SORT, sort, order, default=[Run.created_at.desc()], tiebreak=Run.id)
    rows = db.execute(query.order_by(*clauses).limit(limit).offset(offset)).all()
    counts = artifact_count(db, [str(row[0]) for row in rows])
    return [
        AdminRun(
            id=row[0], project_id=row[1], project_name=row[2], operation=row[3], status=row[4], username=row[5],
            created_at=row[6], finished_at=row[7], size_bytes=row[8], artifacts_count=counts.get(row[0], 0),
        )
        for row in rows
    ], total  # fmt: skip


def _folder(run: Run, settings: Settings) -> Any:
    if not run.workspace_path:
        return None
    try:
        return run_dir(settings.workspace_dir, run.workspace_path)
    except UnsafePathError:
        logger.warning("Ruta de run fuera del workspace", extra={"run_id": run.id})
        return None


def _remove_folders(folders: list[tuple[str, Any]]) -> None:
    """Borra las carpetas **después** del commit: si falla, queda una carpeta huérfana (log), no una fila rota."""
    for run_id, folder in folders:
        if folder is None:
            continue
        try:
            remove_tree(folder)
        except OSError:
            logger.warning("No se pudo borrar la carpeta de la ejecución", extra={"run_id": run_id})


def _summary(run: Run) -> dict[str, Any]:
    return {
        "project_id": run.project_id,
        "operation": run.operation,
        "user_id": run.user_id,
        "status": run.status,
        "size_bytes": run.size_bytes,
    }


def delete_run(db: Session, actor: User, run_id: str, *, settings: Settings, ctx: RequestContext) -> None:
    """Borra la ejecución (fila, artefactos por cascada y carpeta).

    Raises:
        RunNotFoundError: No existe.
        RunStateError: En cola o en curso, o un volcado con constraints sin restaurar (G31).
    """
    run = db.get(Run, run_id)
    if run is None:
        raise RunNotFoundError()
    if run.status not in DELETABLE:
        raise RunStateError("Solo se eliminan ejecuciones terminadas: cancélala o espera a que termine.")
    if dump_journal(run, settings) is not None:
        raise RunStateError(
            "Este volcado dejó constraints sin restaurar en el destino: restáuralas antes de eliminarlo."
        )
    folder = _folder(run, settings)
    audit.record(
        db, action=AuditAction.RUN_DELETE, ctx=ctx, actor_id=actor.id, target_type="run", target_id=run.id,
        details=_summary(run),
    )  # fmt: skip
    db.delete(run)
    db.commit()
    _remove_folders([(run_id, folder)])


def project_runs_summary(db: Session, project_id: int) -> tuple[Project, int, int]:
    """Proyecto, número de ejecuciones y bytes que ocupan (para el modal de confirmación).

    Raises:
        ProjectNotFoundError: No existe.
    """
    project = db.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError()
    count, size = db.execute(
        select(func.count(), func.coalesce(func.sum(Run.size_bytes), 0)).where(Run.project_id == project_id)
    ).one()
    return project, int(count), int(size)


def delete_project_runs(
    db: Session, actor: User, project_id: int, confirm: str, *, settings: Settings, ctx: RequestContext
) -> ProjectRunsDeletion:
    """Borra las ejecuciones terminadas del proyecto; omite las activas y los volcados pendientes (D3).

    Raises:
        ProjectNotFoundError: No existe.
        DeleteConfirmationError: ``confirm`` no es el nombre exacto del proyecto (validado aquí, no solo en la UI).
    """
    project = db.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError()
    if confirm != project.name:
        raise DeleteConfirmationError()
    runs = list(db.scalars(select(Run).where(Run.project_id == project_id)).unique().all())
    active = [r for r in runs if r.status not in DELETABLE]
    candidates = [r for r in runs if r.status in DELETABLE]
    pending = [r for r in candidates if dump_journal(r, settings) is not None]
    chosen = [r for r in candidates if r not in pending]
    folders = [(r.id, _folder(r, settings)) for r in chosen]
    freed = sum(r.size_bytes for r in chosen)
    ids = [r.id for r in chosen]
    result = ProjectRunsDeletion(len(chosen), len(active), len(pending), freed)
    audit.record(
        db, action=AuditAction.PROJECT_RUNS_DELETE, ctx=ctx, actor_id=actor.id, target_type="project",
        target_id=project.id, details={"name": project.name, **vars(result)},
    )  # fmt: skip
    if ids:
        db.execute(delete(Artifact).where(Artifact.run_id.in_(ids)))
        db.execute(delete(Run).where(Run.id.in_(ids)))
    db.commit()
    db.expire_all()
    _remove_folders(folders)
    return result
