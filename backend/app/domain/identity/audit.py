"""Registro de auditoría de acciones de identidad y administración."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Literal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import AuditEntry, User
from app.domain.sorting import SortOrder, like_pattern, order_by


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
    RUN_DELETE: Final = "run.delete"
    PROJECT_RUNS_DELETE: Final = "project.runs_delete"
    SQL_EXECUTE: Final = "sql.execute"
    QUERY_EXECUTE: Final = "query.execute"
    QUERY_CREATE: Final = "query.create"
    QUERY_UPDATE: Final = "query.update"
    QUERY_DELETE: Final = "query.delete"
    UPLOAD_CREATE: Final = "upload.create"
    UPLOAD_DELETE: Final = "upload.delete"
    TEMPLATE_CREATE: Final = "template.create"
    TEMPLATE_UPDATE: Final = "template.update"
    TEMPLATE_DELETE: Final = "template.delete"
    STORAGE_UPDATE: Final = "storage.update"
    STORAGE_MAINTENANCE: Final = "storage.maintenance"


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


AuditSort = Literal["ts", "action", "outcome", "actor", "target"]
_AUDIT_SORT: Final[dict[str, Any]] = {
    "ts": AuditEntry.ts,
    "action": AuditEntry.action,
    "outcome": AuditEntry.outcome,
    "actor": func.lower(func.coalesce(User.username, "")),
    "target": func.coalesce(AuditEntry.target_type, ""),
}


def list_entries(
    db: Session,
    *,
    action: str | None,
    actor_id: int | None,
    limit: int,
    offset: int,
    q: str | None = None,
    sort: AuditSort | None = None,
    order: SortOrder | None = None,
) -> tuple[list[AuditEntry], int]:
    """Eventos (más recientes primero si no se pide otro orden), filtrados por acción (prefijo), actor y ``q`` (acción,
    actor, objetivo o IP)."""
    query = select(AuditEntry).join(User, User.id == AuditEntry.actor_user_id, isouter=True)
    if action:
        query = query.where(AuditEntry.action.startswith(action, autoescape=True))
    if actor_id is not None:
        query = query.where(AuditEntry.actor_user_id == actor_id)
    if q and q.strip():
        pattern = like_pattern(q)
        query = query.where(
            or_(
                func.lower(AuditEntry.action).like(pattern, escape="\\"),
                func.lower(func.coalesce(User.username, "")).like(pattern, escape="\\"),
                func.lower(func.coalesce(AuditEntry.target_type, "")).like(pattern, escape="\\"),
                func.lower(func.coalesce(AuditEntry.target_id, "")).like(pattern, escape="\\"),
                func.lower(func.coalesce(AuditEntry.ip, "")).like(pattern, escape="\\"),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    clauses = order_by(_AUDIT_SORT, sort, order, default=[AuditEntry.id.desc()], tiebreak=AuditEntry.id)
    rows = db.scalars(query.order_by(*clauses).limit(limit).offset(offset)).unique().all()
    return list(rows), total
