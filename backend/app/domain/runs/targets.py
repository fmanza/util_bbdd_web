"""Escrituras en una BD destino (ADR-008/009/010): una sola a la vez por destino (migración, volcado, carga o
restauración de constraints) y las comprobaciones comunes al encolarlas.

``migrations.check_apply``, ``dumps.check_apply``, ``dumps.check_restore`` y ``bulks.check_apply`` son secuencias de
estas funciones más las reglas propias de cada operación; el orden de las llamadas decide qué error ve el usuario.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError, field_error
from app.db.models import TERMINAL_STATUSES, ProjectConnection, Run, User, utcnow
from app.domain.projects.service import Membership
from app.domain.runs.errors import RunParamsError, RunStateError
from app.i18n import Msg

WRITE_OPERATIONS: Final = ("migrate_apply", "dump_apply", "bulk_apply", "dump_restore")
#: Permiso que exige cada escritura y su nombre en los mensajes.
_PERMISSION_NAMES: Final = {
    "ddl.apply": Msg("runs.permission.ddl_apply"),
    "data.write": Msg("runs.permission.data_write"),
}


def _target_alias(db: Session, run: Run) -> str | None:
    """Alias destino de una escritura: en el propio run (migración), en su vista previa (volcado, carga) o en el
    volcado cuyas constraints restaura."""
    if run.operation == "migrate_apply":
        return str(run.params.get("target_connection"))
    if run.operation == "dump_restore":
        dump = db.get(Run, run.params.get("dump_run")) if run.params.get("dump_run") else None
        return _target_alias(db, dump) if dump is not None else None
    preview = db.get(Run, run.params.get("preview_run")) if run.params.get("preview_run") else None
    return str(preview.params.get("target_connection")) if preview is not None else None


def active_write(db: Session, project_id: int, alias: str) -> str | None:
    """Operación de escritura en cola o en curso sobre ``alias`` en el proyecto (``None`` si no hay)."""
    runs = db.scalars(
        select(Run).where(
            Run.project_id == project_id,
            Run.operation.in_(WRITE_OPERATIONS),
            Run.status.not_in((*TERMINAL_STATUSES, "purged")),
        )
    ).all()
    return next((run.operation for run in runs if _target_alias(db, run) == alias), None)


# --- comprobaciones al encolar una escritura ---------------------------------------------------------------------


def params_error(field: str, message: Msg) -> RunParamsError:
    """422 con el error en ``params.<field>``."""
    return RunParamsError(message, errors=[field_error(["body", "params", field], message)])


def check_writer(
    user: User, membership: Membership, *, permission: str, error: type[AppError], owner_only: Msg
) -> None:
    """El usuario tiene ``permission`` (``ddl.apply`` o ``data.write``) y es propietario del proyecto (403)."""
    if not user.can(permission):
        raise error(Msg("runs.missing_permission", permission=_PERMISSION_NAMES[permission]))
    if membership.role != "owner":
        raise error(owner_only)


def load_fresh_preview(
    db: Session,
    membership: Membership,
    params: dict[str, Any],
    settings: Settings,
    *,
    load: Callable[[Session, Run, Settings], dict[str, Any]],
    max_age: timedelta,
) -> tuple[Run, dict[str, Any]]:
    """Vista previa ``params["preview_run"]`` del proyecto, legible y de hace menos de ``max_age`` (422)."""
    run = db.get(Run, params["preview_run"])
    if run is None or run.project_id != membership.project.id:
        raise params_error("preview_run", Msg("runs.preview_missing"))
    try:
        preview = load(db, run, settings)
    except AppError:
        raise params_error("preview_run", Msg("runs.preview_invalid")) from None
    if run.finished_at is None or utcnow() - run.finished_at > max_age:
        raise params_error("preview_run", Msg("runs.preview_expired"))
    return run, preview


def check_target(link: ProjectConnection, engine: object, *, field: str, engine_msg: Msg) -> None:
    """La conexión destino admite escrituras y es del motor con el que se preparó la escritura (422)."""
    if link.connection.read_only:
        raise params_error(field, Msg("runs.target_read_only"))
    if link.connection.db_type != engine:
        raise params_error(field, engine_msg)


def check_confirm(params: dict[str, Any], alias: str) -> None:
    """``confirm`` es el alias del destino, escrito tal cual (422)."""
    if params.get("confirm") != alias:
        raise params_error("confirm", Msg("runs.confirm_alias"))


def check_no_write(db: Session, project_id: int, alias: str, message: Msg) -> None:
    """Ninguna otra escritura en cola o en curso sobre el destino (409)."""
    if active_write(db, project_id, alias):
        raise RunStateError(message)
