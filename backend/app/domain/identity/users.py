"""Administración de usuarios: alta, edición, desactivación, reactivación, desbloqueo y borrado.

El borrado solo se permite si nada depende del usuario (ADR-013): ni proyectos (como miembro o como creador, porque la
carpeta del proyecto en el workspace es la del creador) ni conexiones compartidas o asociadas a proyectos. Siempre
debe quedar un administrador activo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final, Literal

from sqlalchemy import and_, exists, func, not_, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    ColorScheme,
    Connection,
    Project,
    ProjectConnection,
    ProjectMember,
    Role,
    User,
    utcnow,
)
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.identity.errors import (
    LastAdminError,
    SelfDeletionError,
    SelfModificationError,
    UserInUseError,
    UsernameTakenError,
    UserNotFoundError,
)
from app.domain.identity.passwords import check_policy, hash_password
from app.domain.identity.roles import check_grant
from app.domain.identity.sessions import revoke_user_sessions
from app.domain.sorting import SortOrder, like_pattern, order_by
from app.workspace.layout import remove_tree, safe_path

logger = logging.getLogger(__name__)


def normalize_username(username: str) -> str:
    """Los nombres de usuario no distinguen mayúsculas."""
    return username.strip().lower()


@dataclass(frozen=True)
class UserChanges:
    """Cambios de un ``PATCH``; ``None`` significa «sin cambio»."""

    display_name: str | None = None
    #: Rol nuevo (ADR-014).
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = None
    #: Cuota propia en MB (ADR-012); con ``global_storage_quota`` se quita y vuelve a usar la global.
    storage_quota_mb: int | None = None
    global_storage_quota: bool = False


def get_user(db: Session, user_id: int) -> User:
    """Usuario por id.

    Raises:
        UserNotFoundError: No existe.
    """
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFoundError()
    return user


def get_by_username(db: Session, username: str) -> User | None:
    """Usuario por nombre (normalizado) o ``None``."""
    return db.scalar(select(User).where(User.username == normalize_username(username)))


UserSort = Literal["username", "display_name", "role", "created_at", "projects"]
#: ``active`` = activo y sin bloqueo por intentos; ``locked`` = activo con ``locked_until`` futuro.
UserStatus = Literal["active", "inactive", "locked"]

#: Proyectos de los que el usuario es miembro (subconsulta correlacionada con ``users``).
_PROJECT_COUNT: Final = select(func.count()).where(ProjectMember.user_id == User.id).correlate(User).scalar_subquery()

#: Nombre del rol del usuario (subconsulta correlacionada con ``users``).
_ROLE_NAME: Final = select(func.lower(Role.name)).where(Role.id == User.role_id).correlate(User).scalar_subquery()

_USER_SORT: Final[dict[str, Any]] = {
    "username": User.username,
    "display_name": func.lower(User.display_name),
    "role": _ROLE_NAME,
    "created_at": User.created_at,
    "projects": _PROJECT_COUNT,
}


def project_count(db: Session, user_id: int) -> int:
    """Proyectos de los que ``user_id`` es miembro."""
    return db.scalar(select(func.count()).where(ProjectMember.user_id == user_id)) or 0


def list_users(
    db: Session,
    *,
    q: str | None,
    limit: int,
    offset: int,
    sort: UserSort | None = None,
    order: SortOrder | None = None,
    role_id: int | None = None,
    status: UserStatus | None = None,
    now: datetime | None = None,
) -> tuple[list[tuple[User, int]], int]:
    """Usuarios con su número de proyectos (por nombre de usuario si no se pide otro orden), filtrados por texto en
    usuario o nombre visible, rol y estado."""
    query = select(User, _PROJECT_COUNT.label("project_count"))
    if role_id is not None:
        query = query.where(User.role_id == role_id)
    if status is not None:
        locked = and_(User.locked_until.is_not(None), User.locked_until > (now or utcnow()))
        if status == "inactive":
            query = query.where(User.is_active.is_(False))
        elif status == "locked":
            query = query.where(User.is_active.is_(True), locked)
        else:
            query = query.where(User.is_active.is_(True), not_(locked))
    if q and q.strip():
        pattern = like_pattern(q)
        query = query.where(
            or_(
                func.lower(User.username).like(pattern, escape="\\"),
                func.lower(User.display_name).like(pattern, escape="\\"),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    clauses = order_by(_USER_SORT, sort, order, default=[User.username], tiebreak=User.id)
    rows = db.execute(query.order_by(*clauses).limit(limit).offset(offset)).all()
    return [(user, count) for user, count in rows], total


def count_active_admins(db: Session) -> int:
    """Administradores activos (los bloqueados por intentos cuentan: el bloqueo es temporal)."""
    return (
        db.scalar(
            select(func.count())
            .select_from(User)
            .join(Role, Role.id == User.role_id)
            .where(Role.builtin == "admin", User.is_active.is_(True))
        )
        or 0
    )


def create_user(
    db: Session,
    *,
    username: str,
    display_name: str,
    password: str,
    role: Role,
    settings: Settings,
    ctx: RequestContext,
    actor_id: int | None,
    is_active: bool = True,
    storage_quota_mb: int | None = None,
) -> User:
    """Crea un usuario (activo salvo que se pida otra cosa) con su rol y cuota, y lo audita.

    El router comprueba antes que quien da de alta tiene los permisos del rol (``check_grant``); la CLI no.

    Raises:
        UsernameTakenError: El nombre ya existe.
        PasswordPolicyError: La contraseña no cumple la política.
    """
    username = normalize_username(username)
    check_policy(password, username=username, min_length=settings.password_min_length)
    if get_by_username(db, username) is not None:
        raise UsernameTakenError()
    user = User(
        username=username,
        display_name=display_name.strip() or username,
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
        storage_quota_mb=storage_quota_mb,
        failed_attempts=0,
    )
    user.sync_legacy_columns()
    db.add(user)
    db.flush()
    audit.record(
        db,
        action=AuditAction.USER_CREATE,
        ctx=ctx,
        actor_id=actor_id,
        target_type="user",
        target_id=user.id,
        details={
            "username": user.username,
            "role": role.name,
            "is_active": is_active,
            "storage_quota_mb": storage_quota_mb,
        },
    )
    db.commit()
    return user


def update_user(
    db: Session, user: User, changes: UserChanges, *, actor: User, settings: Settings, ctx: RequestContext
) -> User:
    """Aplica ``changes`` a ``user``.

    Desactivar o restablecer la contraseña revoca las sesiones del usuario; reactivar o restablecer la contraseña
    quita el bloqueo por intentos.

    Cambiar el rol exige tener todos los permisos del rol actual y del nuevo (nadie da ni quita lo que no tiene) y
    cierra sus sesiones.

    Raises:
        SelfModificationError: Intenta desactivarse o cambiar su propio rol.
        PermissionEscalationError: El rol actual o el nuevo tiene permisos que ``actor`` no tiene.
        LastAdminError: Quedaría el sistema sin administradores activos.
        PasswordPolicyError: La contraseña nueva no cumple la política.
    """
    new_role = changes.role if changes.role is not None and changes.role.id != user.role_id else None
    if user.id == actor.id and (new_role is not None or changes.is_active is False):
        raise SelfModificationError()
    if new_role is not None:
        check_grant(actor, set(user.permissions) | set(new_role.permission_list))
    loses_admin = (
        user.is_admin
        and user.is_active
        and ((new_role is not None and new_role.builtin != "admin") or changes.is_active is False)
    )
    if loses_admin and count_active_admins(db) <= 1:
        raise LastAdminError()

    changed: list[str] = []
    if changes.display_name is not None and changes.display_name.strip() != user.display_name:
        user.display_name = changes.display_name.strip() or user.username
        changed.append("display_name")
    previous_role = user.role.name
    if new_role is not None:
        user.role = new_role
        user.sync_legacy_columns()
        revoke_user_sessions(db, user.id)
        changed.append("role")
    quota = None if changes.global_storage_quota else changes.storage_quota_mb
    if (changes.global_storage_quota or quota is not None) and quota != user.storage_quota_mb:
        user.storage_quota_mb = quota
        changed.append("storage_quota_mb")
    if changes.password is not None:
        check_policy(changes.password, username=user.username, min_length=settings.password_min_length)
        user.password_hash = hash_password(changes.password)
        user.password_changed_at = utcnow()
        user.failed_attempts = 0
        user.locked_until = None
        revoke_user_sessions(db, user.id)
        audit.record(
            db,
            action=AuditAction.USER_PASSWORD_RESET,
            ctx=ctx,
            actor_id=actor.id,
            target_type="user",
            target_id=user.id,
        )
    if changes.is_active is not None and changes.is_active != user.is_active:
        user.is_active = changes.is_active
        if changes.is_active:
            user.failed_attempts = 0
            user.locked_until = None
        else:
            revoke_user_sessions(db, user.id)
        audit.record(
            db,
            action=AuditAction.USER_REACTIVATE if changes.is_active else AuditAction.USER_DEACTIVATE,
            ctx=ctx,
            actor_id=actor.id,
            target_type="user",
            target_id=user.id,
        )
    if changed:
        audit.record(
            db,
            action=AuditAction.USER_UPDATE,
            ctx=ctx,
            actor_id=actor.id,
            target_type="user",
            target_id=user.id,
            details={
                "fields": changed,
                **({"role": [previous_role, user.role.name]} if "role" in changed else {}),
                **({"storage_quota_mb": user.storage_quota_mb} if "storage_quota_mb" in changed else {}),
            },
        )
    if loses_admin:
        _ensure_active_admin(db)
    db.commit()
    return user


def _ensure_active_admin(db: Session) -> None:
    """Vuelve a contar tras escribir: dos peticiones simultáneas podían ver dos admins y quitar uno cada una.

    Raises:
        LastAdminError: Ya no queda ningún administrador activo (se deshace la operación).
    """
    db.flush()
    if count_active_admins(db) == 0:
        db.rollback()
        raise LastAdminError()


def unlock_user(db: Session, user: User, *, actor: User, ctx: RequestContext) -> User:
    """Quita el bloqueo por intentos fallidos y pone el contador a cero; se audita si había algo que quitar."""
    if user.failed_attempts or user.locked_until is not None:
        user.failed_attempts = 0
        user.locked_until = None
        audit.record(
            db, action=AuditAction.USER_UNLOCK, ctx=ctx, actor_id=actor.id, target_type="user", target_id=user.id
        )
        db.commit()
    return user


@dataclass(frozen=True)
class ProjectRef:
    """Proyecto que impide borrar un usuario; ``role`` es su rol de miembro (``None`` en los que solo creó)."""

    id: int
    name: str
    role: str | None = None


@dataclass(frozen=True)
class ConnectionRef:
    """Conexión que impide borrar un usuario (compartida o asociada a algún proyecto)."""

    id: int
    name: str
    visibility: str


#: Motivos por los que no se puede borrar un usuario.
DeletionReason = Literal["self", "last_admin", "member", "creator", "connections"]


@dataclass(frozen=True)
class DeletionCheck:
    """Lo que impide borrar un usuario (todo vacío si se puede)."""

    reasons: list[DeletionReason] = field(default_factory=list)
    projects: list[ProjectRef] = field(default_factory=list)
    created_projects: list[ProjectRef] = field(default_factory=list)
    connections: list[ConnectionRef] = field(default_factory=list)

    @property
    def can_delete(self) -> bool:
        return not self.reasons

    def as_extra(self) -> dict[str, object]:
        """Campos adicionales del *problem details* del ``409``."""
        return {
            "reasons": list(self.reasons),
            "projects": [{"id": p.id, "name": p.name, "role": p.role} for p in self.projects],
            "created_projects": [{"id": p.id, "name": p.name} for p in self.created_projects],
            "connections": [{"id": c.id, "name": c.name, "visibility": c.visibility} for c in self.connections],
        }


def deletion_check(db: Session, user: User, *, actor: User) -> DeletionCheck:
    """Comprueba si ``actor`` puede borrar ``user`` y, si no, por qué."""
    reasons: list[DeletionReason] = []
    if user.id == actor.id:
        reasons.append("self")
    if user.is_admin and user.is_active and count_active_admins(db) <= 1:
        reasons.append("last_admin")
    projects = [
        ProjectRef(id=pid, name=name, role=role)
        for pid, name, role in db.execute(
            select(Project.id, Project.name, ProjectMember.role)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(ProjectMember.user_id == user.id)
            .order_by(func.lower(Project.name), Project.id)
        ).all()
    ]
    created = [
        ProjectRef(id=pid, name=name)
        for pid, name in db.execute(
            select(Project.id, Project.name)
            .where(Project.owner_id == user.id)
            .order_by(func.lower(Project.name), Project.id)
        ).all()
    ]
    linked = exists().where(ProjectConnection.connection_id == Connection.id)
    connections = [
        ConnectionRef(id=cid, name=name, visibility=visibility)
        for cid, name, visibility in db.execute(
            select(Connection.id, Connection.name, Connection.visibility)
            .where(Connection.owner_id == user.id, or_(Connection.visibility == "shared", linked))
            .order_by(func.lower(Connection.name), Connection.id)
        ).all()
    ]
    if projects:
        reasons.append("member")
    if created:
        reasons.append("creator")
    if connections:
        reasons.append("connections")
    return DeletionCheck(reasons=reasons, projects=projects, created_projects=created, connections=connections)


def delete_user(db: Session, user: User, *, actor: User, settings: Settings, ctx: RequestContext) -> None:
    """Borra ``user`` si nada depende de él (ADR-013).

    Con él se borran sus sesiones y sus conexiones privadas sin proyectos; las ejecuciones, ficheros, plantillas y
    eventos de auditoría que lo referencian quedan sin usuario (la auditoría conserva su nombre). Su carpeta del
    workspace se borra si no contiene ficheros.

    Raises:
        SelfDeletionError: Es la cuenta de ``actor``.
        LastAdminError: Es el último administrador activo.
        UserInUseError: Es miembro o creador de proyectos, o tiene conexiones compartidas o en uso.
    """
    # Escribir primero toma el bloqueo de escritura de SQLite: entre la comprobación y el borrado nadie puede añadirlo
    # a un proyecto ni asociar sus conexiones (los ``ON DELETE CASCADE`` se las llevarían sin aviso).
    user.updated_at = utcnow()
    db.flush()
    check = deletion_check(db, user, actor=actor)
    if not check.can_delete:
        db.rollback()
        if "self" in check.reasons:
            raise SelfDeletionError()
        if "last_admin" in check.reasons:
            raise LastAdminError()
        raise UserInUseError(
            "Es miembro o creador de proyectos, o tiene conexiones compartidas o en uso.", **check.as_extra()
        )
    user_id, was_admin = user.id, user.is_admin
    private = db.scalar(select(func.count()).where(Connection.owner_id == user_id)) or 0
    audit.record(
        db,
        action=AuditAction.USER_DELETE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="user",
        target_id=user_id,
        details={"username": user.username, "role": user.role.name, "connections_deleted": private},
    )
    db.delete(user)
    if was_admin:
        _ensure_active_admin(db)
    db.commit()
    _remove_empty_user_folder(settings, user_id)


def _remove_empty_user_folder(settings: Settings, user_id: int) -> None:
    """Borra ``users/<id>/`` del workspace si no queda ningún fichero (sin proyectos creados no debería haberlos)."""
    folder = safe_path(settings.workspace_dir, f"users/{int(user_id)}")
    if not folder.is_dir():
        return
    if any(path.is_file() for path in folder.rglob("*")):
        logger.warning("Carpeta de un usuario borrado con ficheros: se conserva", extra={"user_id": user_id})
        return
    remove_tree(folder)


def update_preferences(
    db: Session, user: User, *, color_scheme: ColorScheme | None = None, language: str | None = None
) -> User:
    """Guarda las preferencias de ``user`` (su propia cuenta): las que lleguen (``None`` = sin cambio).

    Sin auditoría: son preferencias de presentación sin efecto en la seguridad (sesiones 2026-11-23-tema-color y
    2026-11-25-roles-idioma).
    """
    changed = False
    if color_scheme is not None and user.color_scheme != color_scheme:
        user.color_scheme = color_scheme
        changed = True
    if language is not None and user.language != language:
        user.language = language
        changed = True
    if changed:
        db.commit()
    return user
