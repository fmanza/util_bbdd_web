"""Volcado de datos (Fase 8, ADR-009): vista previa guardada y reglas para encolar ``dump_apply``.

``dump_preview`` es el modo seco (solo lee). Escribir filas en la BD destino exige, **al encolar**:

1. Permiso ``users.can_write_data`` (lo concede un admin) y rol ``owner`` en el proyecto.
2. Una ``dump_preview`` correcta del mismo proyecto de hace menos de ``PREVIEW_MAX_AGE``: el volcado usa **sus**
   parámetros (no se pueden cambiar entre la revisión y la ejecución).
3. Las conexiones de la vista previa siguen en el proyecto con el **mismo id** (un alias reasignado a otra
   conexión no vale), el destino **no** ``read_only`` y del mismo motor.
4. ``confirm`` igual al alias del destino y, si la vista previa vacía el destino, ``confirm_truncate`` = «VACIAR».
5. Ninguna otra escritura (volcado o migración) activa sobre ese destino en el proyecto.
6. Ningún volcado anterior sobre ese destino con constraints sin restaurar (diario pendiente, G31).

El job vuelve a comprobarlo y exige la misma estructura (``structure_hash``) antes de escribir.

Si el proceso de un volcado muere (timeout, caída) con las constraints desactivadas, queda su diario
(``DUMP_JOURNAL_PATH``). ``dump_restore`` las reactiva con los mismos controles que el volcado (permiso, owner, la
misma conexión destino, no ``read_only``, confirmación con el alias); el worker la encola solo al cerrar un volcado
cuyo proceso murió (``enqueue_automatic_restore``).
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.ulid import new_ulid
from app.db.models import TERMINAL_STATUSES, ProjectConnection, Run, User, utcnow
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.projects.service import Membership, get_project_connection
from app.domain.runs.errors import ArtifactNotFoundError, RunParamsError, RunStateError
from app.domain.runs.service import ACTIVE_STATUSES, DUMP_TARGET_PATH, dump_journal, get_artifact_by_path
from app.domain.runs.targets import active_write
from app.workspace.layout import run_dir, run_relative_path

PREVIEW_PATH: Final = "outputs/dump/preview.json"
RESULT_PATH: Final = "outputs/dump/result.json"
JSON_MAX_BYTES: Final = 20 * 1024 * 1024
PREVIEW_MAX_AGE: Final = timedelta(minutes=60)
TRUNCATE_WORD: Final = "VACIAR"


class DumpForbiddenError(AppError):
    status = 403
    title = "No puedes volcar datos en este proyecto"


class DumpNotAvailableError(AppError):
    status = 404
    title = "Esta ejecución no tiene una vista previa o un resultado de volcado"


class DumpTooLargeError(AppError):
    status = 413
    title = "El documento es demasiado grande para el visor; descarga el informe"


def _params_error(field: str, message: str) -> RunParamsError:
    return RunParamsError(message, errors=[{"loc": ["body", "params", field], "msg": message, "type": "value_error"}])


def _load(db: Session, run: Run, path: str, settings: Settings) -> dict[str, Any]:
    try:
        artifact, file = get_artifact_by_path(db, run, path, settings)
    except ArtifactNotFoundError:
        raise DumpNotAvailableError() from None
    if artifact.size_bytes > JSON_MAX_BYTES:
        raise DumpTooLargeError()
    data: dict[str, Any] = json.loads(file.read_text(encoding="utf-8"))
    return data


def load_preview(db: Session, run: Run, settings: Settings) -> dict[str, Any]:
    """Vista previa de una ``dump_preview`` correcta.

    Raises:
        DumpNotAvailableError: No es una vista previa correcta, o está purgada.
    """
    if run.operation != "dump_preview" or run.status != "succeeded":
        raise DumpNotAvailableError()
    return _load(db, run, PREVIEW_PATH, settings)


def load_result(db: Session, run: Run, settings: Settings) -> dict[str, Any]:
    """Resultado de un ``dump_apply`` terminado (también si falló a medias)."""
    if run.operation != "dump_apply":
        raise DumpNotAvailableError()
    return _load(db, run, RESULT_PATH, settings)


def check_apply(db: Session, user: User, membership: Membership, params: dict[str, Any], settings: Settings) -> None:
    """Reglas de ADR-009 para ``dump_apply`` (ver la cabecera del módulo).

    Raises:
        DumpForbiddenError: Sin permiso o sin rol owner (403).
        RunParamsError: Vista previa, destino o confirmaciones no válidos (422).
        RunStateError: Otro volcado en curso sobre el destino (409).
    """
    if not user.can_write_data:
        raise DumpForbiddenError("Necesitas el permiso «Puede escribir datos»; pídeselo a un administrador.")
    if membership.role != "owner":
        raise DumpForbiddenError("Solo el propietario del proyecto puede volcar datos.")
    preview_run = db.get(Run, params["preview_run"])
    if preview_run is None or preview_run.project_id != membership.project.id:
        raise _params_error("preview_run", "La vista previa no existe en este proyecto.")
    try:
        preview = load_preview(db, preview_run, settings)
    except AppError:
        raise _params_error("preview_run", "La ejecución indicada no es una vista previa correcta.") from None
    if preview_run.finished_at is None or utcnow() - preview_run.finished_at > PREVIEW_MAX_AGE:
        raise _params_error("preview_run", "La vista previa tiene más de 60 minutos: repítela.")
    alias = str(preview_run.params["target_connection"])
    changed = connections_changed(db, membership.project, preview_run.params, preview)
    if changed:
        raise _params_error("preview_run", changed)
    link = get_project_connection(db, membership.project, alias)
    if link.connection.read_only:
        raise _params_error("preview_run", "La conexión destino es de solo lectura.")
    if link.connection.db_type != preview.get("target_engine"):
        raise _params_error("preview_run", f"La conexión destino ya no es {preview.get('target_engine')}.")
    if params.get("confirm") != alias:
        raise _params_error("confirm", "Escribe el alias de la conexión destino para confirmar.")
    if preview.get("truncate_target") and params.get("confirm_truncate") != TRUNCATE_WORD:
        raise _params_error("confirm_truncate", f"Escribe «{TRUNCATE_WORD}» para confirmar que se vacía el destino.")
    if active_write(db, membership.project.id, alias):
        raise RunStateError("Ya hay un volcado o una migración en curso sobre esa conexión destino.")
    pending = pending_restore(db, membership.project.id, alias, settings)
    if pending:
        raise RunStateError(
            f"El volcado {pending} dejó constraints sin restaurar en «{alias}»: restáuralas antes de volver a volcar."
        )


def connections_changed(db: Session, project: Any, params: dict[str, Any], preview: dict[str, Any]) -> str | None:
    """Motivo por el que las conexiones ya no son las de la vista previa (``None`` si siguen siendo las mismas).

    La vista previa guarda el id de cada conexión: un alias quitado y asociado a otra conexión del mismo motor y con
    las mismas tablas daría la misma huella de estructura y escribiría en una BD que no se revisó.
    """
    for side in ("source", "target"):
        alias = str(params[f"{side}_connection"])
        try:
            link = get_project_connection(db, project, alias)
        except AppError:
            return f"El proyecto ya no tiene la conexión «{alias}»."
        if link.connection_id != preview.get(f"{side}_connection_id"):
            return f"La conexión «{alias}» ya no es la de la vista previa: repítela."
    return None


# --- constraints sin restaurar (G31) -----------------------------------------------------------------------------

#: Formato del diario de util_bbdd (``util_bbdd.dump._constraints.JOURNAL_FORMAT``, 4.4.0) y motor de cada dialecto.
JOURNAL_FORMAT: Final = "util_bbdd.dump_constraints_journal"
JOURNAL_MAX_BYTES: Final = 5 * 1024 * 1024
_JOURNAL_ENGINES: Final = {"mssql": "sqlserver", "oracle": "oracle", "postgresql": "postgresql"}


def read_journal(path: Path) -> dict[str, Any] | None:
    """Lo que muestra la web de un diario: motor, tablas, constraints y fecha (``None`` si no es un diario válido)."""
    try:
        if path.stat().st_size > JOURNAL_MAX_BYTES:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("format") != JOURNAL_FORMAT:
        return None
    pairs = data.get("constraints")
    tables = data.get("tables")
    pairs = pairs if isinstance(pairs, list) else []
    return {
        "engine": _JOURNAL_ENGINES.get(str(data.get("dialect"))),
        "tables": [t for t in tables if isinstance(t, str)] if isinstance(tables, list) else [],
        "constraints": [
            {"table": p[0], "constraint": p[1]}
            for p in pairs
            if isinstance(p, list) and len(p) == 2 and all(isinstance(x, str) for x in p)
        ],
        "created_at": data["created_at"] if isinstance(data.get("created_at"), str) else None,
    }


def dump_target(run: Run, settings: Settings) -> dict[str, Any] | None:
    """Conexión destino que el job del volcado anotó junto al diario (``{"alias", "connection_id"}``)."""
    if not run.workspace_path:
        return None
    try:
        data = json.loads((run_dir(settings.workspace_dir, run.workspace_path) / DUMP_TARGET_PATH).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("alias"), str)
        or not isinstance(data.get("connection_id"), int)
    ):
        return None
    return data


def _active_restore(db: Session, dump: Run) -> str | None:
    """``dump_restore`` en cola o en curso para ese volcado."""
    runs = db.scalars(
        select(Run).where(
            Run.project_id == dump.project_id, Run.operation == "dump_restore", Run.status.in_(ACTIVE_STATUSES)
        )
    ).all()
    return next((run.id for run in runs if run.params.get("dump_run") == dump.id), None)


def pending_constraints(db: Session, run: Run, settings: Settings) -> dict[str, Any]:
    """Constraints que un ``dump_apply`` dejó desactivadas (diario pendiente) y la restauración en marcha, si la hay.

    Raises:
        DumpNotAvailableError: No es un volcado.
    """
    if run.operation != "dump_apply":
        raise DumpNotAvailableError()
    journal = dump_journal(run, settings)
    if journal is None:
        return {"pending": False, "tables": [], "constraints": []}
    info = read_journal(journal) or {"engine": None, "tables": [], "constraints": [], "created_at": None}
    target = dump_target(run, settings)
    return {
        "pending": True,
        **info,
        "target_connection": target["alias"] if target else None,
        "restore_run": _active_restore(db, run),
    }


def pending_restore(db: Session, project_id: int, alias: str, settings: Settings) -> str | None:
    """Volcado terminado sobre ``alias`` en el proyecto que dejó constraints sin restaurar (``None`` si no hay)."""
    runs = db.scalars(
        select(Run).where(
            Run.project_id == project_id, Run.operation == "dump_apply", Run.status.in_(tuple(TERMINAL_STATUSES))
        )
    ).all()
    for run in runs:
        target = dump_target(run, settings)
        if target is not None and target["alias"] == alias and dump_journal(run, settings) is not None:
            return run.id
    return None


def restore_target(db: Session, project: Any, dump: Run | None, settings: Settings) -> tuple[ProjectConnection, Path]:
    """Conexión destino y diario de un volcado con constraints sin restaurar; mismas reglas que el volcado (ADR-009).

    Raises:
        RunParamsError: No es un volcado terminado del proyecto, no tiene diario, o la conexión destino ya no es la
            misma, es de solo lectura o de otro motor.
    """
    if dump is None or dump.project_id != project.id or dump.operation != "dump_apply":
        raise _params_error("dump_run", "El volcado no existe en este proyecto.")
    journal = dump_journal(dump, settings)
    if journal is None:
        raise _params_error("dump_run", "Este volcado no tiene constraints pendientes de restaurar.")
    target = dump_target(dump, settings)
    info = read_journal(journal)
    if target is None or info is None:
        raise _params_error("dump_run", "El diario de constraints de este volcado no es válido: revísalas a mano.")
    alias = target["alias"]
    try:
        link = get_project_connection(db, project, alias)
    except AppError:
        raise _params_error("dump_run", f"El proyecto ya no tiene la conexión «{alias}».") from None
    if link.connection_id != target["connection_id"]:
        raise _params_error("dump_run", f"La conexión «{alias}» ya no es la del volcado.")
    if link.connection.read_only:
        raise _params_error("dump_run", "La conexión destino es de solo lectura.")
    if link.connection.db_type != info["engine"]:
        raise _params_error("dump_run", f"La conexión destino ya no es {info['engine']}.")
    return link, journal


def check_restore(db: Session, user: User, membership: Membership, params: dict[str, Any], settings: Settings) -> None:
    """Reglas para encolar ``dump_restore``: las del volcado (ADR-009, riesgo S2 del plan de huecos).

    Raises:
        DumpForbiddenError: Sin permiso o sin rol owner (403).
        RunParamsError: Volcado, diario, destino o confirmación no válidos (422).
        RunStateError: Otra escritura en curso sobre el destino (409).
    """
    if not user.can_write_data:
        raise DumpForbiddenError("Necesitas el permiso «Puede escribir datos»; pídeselo a un administrador.")
    if membership.role != "owner":
        raise DumpForbiddenError("Solo el propietario del proyecto puede restaurar constraints.")
    link, _ = restore_target(db, membership.project, db.get(Run, params["dump_run"]), settings)
    if params.get("confirm") != link.alias:
        raise _params_error("confirm", "Escribe el alias de la conexión destino para confirmar.")
    if active_write(db, membership.project.id, link.alias):
        raise RunStateError("Ya hay una escritura en curso sobre esa conexión destino.")


def enqueue_automatic_restore(db: Session, run_id: str, settings: Settings, *, ctx: RequestContext) -> str | None:
    """Encola ``dump_restore`` para un volcado cuyo proceso murió con el diario pendiente (lo llama el worker).

    La lanza en nombre del usuario del volcado y el job aplica los mismos controles que una manual; si no los cumple,
    falla y queda la acción manual. Devuelve el id del run nuevo (``None`` si no hace falta).
    """
    dump = db.get(Run, run_id)
    if dump is None or dump_journal(dump, settings) is None or _active_restore(db, dump) is not None:
        return None
    target = dump_target(dump, settings)
    if target is None:
        return None
    now = utcnow()
    restore_id = new_ulid()
    project = dump.project
    db.add(
        Run(
            id=restore_id,
            project_id=project.id,
            user_id=dump.user_id,
            operation="dump_restore",
            params={"dump_run": dump.id, "confirm": target["alias"]},
            status="queued",
            phase="queued",
            created_at=now,
            workspace_path=run_relative_path(project.owner_id, project.id, now, "dump_restore", restore_id),
        )
    )
    audit.record(
        db, action=AuditAction.RUN_CREATE, ctx=ctx, actor_id=None, target_type="run", target_id=restore_id,
        details={
            "project_id": project.id, "operation": "dump_restore",
            "dump_restore": {"dump_run": dump.id, "target_connection": target["alias"], "automatic": True},
        },
    )  # fmt: skip
    db.commit()
    return restore_id
