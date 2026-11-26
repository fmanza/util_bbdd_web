"""Roles con permisos (ADR-014): alta, edición y borrado, con sus salvaguardas.

Hay dos roles base (``builtin``): «Administrador» (todos los permisos) y «Usuario» (ninguno); no se borran ni cambian
de permisos. Los personalizados los gestiona quien tiene ``roles.manage``, y nadie da ni quita un permiso que no tiene.
Quitar permisos a un rol cierra las sesiones de sus usuarios.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Role, User, utcnow
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.identity.errors import (
    InvalidPermissionError,
    PermissionEscalationError,
    RoleBuiltinError,
    RoleInUseError,
    RoleNameTakenError,
    RoleNotFoundError,
)
from app.domain.identity.permissions import BuiltinRole, normalize, unknown
from app.domain.identity.sessions import revoke_user_sessions
from app.i18n import Msg


@dataclass(frozen=True)
class RoleView:
    """Rol con su número de usuarios."""

    role: Role
    users: int


def builtin_role(db: Session, key: BuiltinRole) -> Role:
    """Rol base ``key`` (lo crea la migración 0014)."""
    role = db.scalar(select(Role).where(Role.builtin == key))
    if role is None:  # pragma: no cover - lo crea la migración 0014
        raise RoleNotFoundError()
    return role


def get_role(db: Session, role_id: int) -> Role:
    """Rol por id.

    Raises:
        RoleNotFoundError: No existe.
    """
    role = db.get(Role, role_id)
    if role is None:
        raise RoleNotFoundError()
    return role


def user_count(db: Session, role_id: int) -> int:
    """Usuarios con el rol ``role_id``."""
    return db.scalar(select(func.count()).where(User.role_id == role_id)) or 0


def list_roles(db: Session) -> list[RoleView]:
    """Roles con su número de usuarios: los base primero («Administrador», «Usuario») y después por nombre."""
    roles = db.scalars(select(Role).order_by(Role.builtin.is_(None), Role.builtin, func.lower(Role.name)))
    counts = {int(rid): int(n) for rid, n in db.execute(select(User.role_id, func.count()).group_by(User.role_id))}
    return [RoleView(role, counts.get(role.id, 0)) for role in roles]


def check_grant(actor: User, permissions: list[str] | set[str]) -> None:
    """``actor`` tiene todos los ``permissions`` (para darlos, quitarlos o asignar un rol que los tiene).

    Raises:
        PermissionEscalationError: Le falta alguno.
    """
    missing = set(permissions) - set(actor.permissions)
    if missing:
        raise PermissionEscalationError(
            Msg("identity.permission_escalation", permissions=", ".join(sorted(missing))), missing=sorted(missing)
        )


def _validated(permissions: list[str]) -> list[str]:
    bad = unknown(permissions)
    if bad:
        raise InvalidPermissionError(Msg("identity.invalid_permission", permissions=", ".join(bad)), unknown=bad)
    return list(normalize(permissions))


def _name_taken(db: Session, name: str, *, exclude: int | None = None) -> bool:
    query = select(Role.id).where(func.lower(Role.name) == name.strip().lower())
    if exclude is not None:
        query = query.where(Role.id != exclude)
    return db.scalar(query) is not None


def create_role(db: Session, *, name: str, permissions: list[str], actor: User, ctx: RequestContext) -> Role:
    """Crea un rol personalizado y lo audita.

    Raises:
        InvalidPermissionError, PermissionEscalationError, RoleNameTakenError.
    """
    granted = _validated(permissions)
    check_grant(actor, granted)
    if _name_taken(db, name):
        raise RoleNameTakenError()
    role = Role(name=name.strip(), permissions=granted, created_by=actor.id)
    db.add(role)
    db.flush()
    audit.record(
        db,
        action=AuditAction.ROLE_CREATE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="role",
        target_id=role.id,
        details={"name": role.name, "permissions": granted},
    )
    db.commit()
    return role


def update_role(
    db: Session, role: Role, *, name: str | None, permissions: list[str] | None, actor: User, ctx: RequestContext
) -> Role:
    """Renombra un rol o cambia sus permisos. Los base no cambian: ni de permisos ni de nombre (la interfaz muestra el
    suyo traducido).

    Quitar permisos cierra las sesiones de quienes tienen el rol (dejan de valer de inmediato).

    Raises:
        RoleBuiltinError, InvalidPermissionError, PermissionEscalationError, RoleNameTakenError.
    """
    changes: dict[str, object] = {}
    if name is not None and name.strip() != role.name:
        if role.builtin is not None:
            raise RoleBuiltinError()
        if _name_taken(db, name, exclude=role.id):
            raise RoleNameTakenError()
        changes["name"] = [role.name, name.strip()]
        role.name = name.strip()
    if permissions is not None:
        granted = _validated(permissions)
        current = role.permission_list
        if granted != current:
            if role.builtin is not None:
                raise RoleBuiltinError()
            check_grant(actor, set(granted) ^ set(current))  # ni dar ni quitar lo que no se tiene
            changes["permissions"] = [current, granted]
            role.permissions = granted
            holders = list(db.scalars(select(User).where(User.role_id == role.id)))
            for holder in holders:
                holder.sync_legacy_columns()
            if set(current) - set(granted):
                for holder in holders:
                    revoke_user_sessions(db, holder.id)
    if changes:
        audit.record(
            db,
            action=AuditAction.ROLE_UPDATE,
            ctx=ctx,
            actor_id=actor.id,
            target_type="role",
            target_id=role.id,
            details=changes,
        )
    db.commit()
    return role


def delete_role(db: Session, role: Role, *, actor: User, ctx: RequestContext) -> None:
    """Borra un rol personalizado sin usuarios.

    Raises:
        RoleBuiltinError, RoleInUseError, PermissionEscalationError.
    """
    if role.builtin is not None:
        raise RoleBuiltinError()
    check_grant(actor, role.permission_list)
    # Escribir primero toma el bloqueo de escritura de SQLite: nadie le asigna usuarios entre la comprobación y el borrado.
    role.updated_at = utcnow()
    db.flush()
    if user_count(db, role.id):
        db.rollback()
        raise RoleInUseError(Msg("identity.role_in_use"))
    audit.record(
        db,
        action=AuditAction.ROLE_DELETE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="role",
        target_id=role.id,
        details={"name": role.name, "permissions": role.permission_list},
    )
    db.delete(role)
    db.commit()
