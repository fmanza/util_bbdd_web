"""Registro de auditoría de acciones de identidad y administración."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AuditEntry


class AuditAction:
    """Acciones auditadas (valor de ``audit_log.action``)."""

    LOGIN: Final = "auth.login"
    LOCKOUT: Final = "auth.lockout"
    LOGOUT: Final = "auth.logout"
    PASSWORD_CHANGE: Final = "auth.password_change"  # noqa: S105 (nombre de acción)
    USER_CREATE: Final = "user.create"
    USER_UPDATE: Final = "user.update"
    USER_DEACTIVATE: Final = "user.deactivate"
    USER_REACTIVATE: Final = "user.reactivate"
    USER_PASSWORD_RESET: Final = "user.password_reset"  # noqa: S105 (nombre de acción)
    SESSION_REVOKE: Final = "session.revoke"
    CONNECTION_CREATE: Final = "connection.create"
    CONNECTION_UPDATE: Final = "connection.update"
    CONNECTION_DELETE: Final = "connection.delete"
    CONNECTION_TEST: Final = "connection.test"
    CONNECTION_READINESS: Final = "connection.readiness"
    ALLOWLIST_CREATE: Final = "allowlist.create"
    ALLOWLIST_DELETE: Final = "allowlist.delete"
    PROJECT_CREATE: Final = "project.create"
    PROJECT_UPDATE: Final = "project.update"
    PROJECT_DELETE: Final = "project.delete"
    PROJECT_MEMBER_ADD: Final = "project.member_add"
    PROJECT_MEMBER_UPDATE: Final = "project.member_update"
    PROJECT_MEMBER_REMOVE: Final = "project.member_remove"
    PROJECT_CONNECTION_ADD: Final = "project.connection_add"
    PROJECT_CONNECTION_REMOVE: Final = "project.connection_remove"
    RUN_CREATE: Final = "run.create"
    RUN_CANCEL: Final = "run.cancel"
    RUN_PURGE: Final = "run.purge"
    SQL_EXECUTE: Final = "sql.execute"
    QUERY_EXECUTE: Final = "query.execute"
    QUERY_CREATE: Final = "query.create"
    QUERY_UPDATE: Final = "query.update"
    QUERY_DELETE: Final = "query.delete"
    UPLOAD_CREATE: Final = "upload.create"
    UPLOAD_DELETE: Final = "upload.delete"


@dataclass(frozen=True)
class RequestContext:
    """Origen de la acción, para auditoría y sesiones.

    Attributes:
        ip: IP del cliente (la que entrega uvicorn con ``--proxy-headers``).
        user_agent: Cabecera ``User-Agent``, truncada a 255 caracteres.
    """

    ip: str | None = None
    user_agent: str | None = None

    def __post_init__(self) -> None:
        if self.user_agent is not None:
            object.__setattr__(self, "user_agent", self.user_agent[:255])


CLI_CONTEXT = RequestContext(ip=None, user_agent="cli")


def record(
    db: Session,
    *,
    action: str,
    ctx: RequestContext,
    actor_id: int | None,
    outcome: str = "success",
    target_type: str | None = None,
    target_id: int | str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditEntry:
    """Añade un evento a la sesión de BD (lo confirma quien llama). ``details`` no debe contener secretos."""
    entry = AuditEntry(
        action=action,
        outcome=outcome,
        actor_user_id=actor_id,
        target_type=target_type,
        target_id=None if target_id is None else str(target_id),
        ip=ctx.ip,
        details=details,
    )
    db.add(entry)
    return entry


def list_entries(
    db: Session, *, action: str | None, actor_id: int | None, limit: int, offset: int
) -> tuple[list[AuditEntry], int]:
    """Eventos más recientes primero, filtrados por acción (prefijo) y actor."""
    query = select(AuditEntry)
    if action:
        query = query.where(AuditEntry.action.startswith(action, autoescape=True))
    if actor_id is not None:
        query = query.where(AuditEntry.actor_user_id == actor_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(AuditEntry.id.desc()).limit(limit).offset(offset)).all()
    return list(rows), total
