"""Proyectos, miembros y conexiones del proyecto.

Permisos (comprobados en el servicio):

| Acción | Rol mínimo |
|---|---|
| Ver proyecto, miembros, conexiones, ejecuciones y artefactos | ``viewer`` |
| Lanzar, cancelar, relanzar y purgar ejecuciones; asociar o quitar conexiones | ``editor`` |
| Editar o borrar el proyecto; gestionar miembros | ``owner`` |

Quien no es miembro recibe 404, también un admin global (coherente con las conexiones privadas).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Project, ProjectConnection, ProjectMember, ProjectRole, Run, User
from app.domain.connections.service import get_visible as get_visible_connection
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.identity.users import get_by_username
from app.domain.projects.errors import (
    AliasTakenError,
    LastOwnerError,
    MemberExistsError,
    MemberNotFoundError,
    ProjectBusyError,
    ProjectConnectionNotFoundError,
    ProjectForbiddenError,
    ProjectNameTakenError,
    ProjectNotFoundError,
)
from app.workspace.layout import remove_tree, safe_path

_RANK: Final[dict[str, int]] = {"viewer": 1, "editor": 2, "owner": 3}


@dataclass(frozen=True)
class Membership:
    """Proyecto visible para un usuario y su rol en él."""

    project: Project
    role: ProjectRole

    def can(self, minimum: ProjectRole) -> bool:
        return _RANK[self.role] >= _RANK[minimum]


def _role(value: str) -> ProjectRole:
    if value == "owner":
        return "owner"
    return "editor" if value == "editor" else "viewer"


def get_membership(db: Session, user: User, project_id: int, minimum: ProjectRole = "viewer") -> Membership:
    """Proyecto y rol de ``user``.

    Raises:
        ProjectNotFoundError: No existe o no es miembro.
        ProjectForbiddenError: Su rol no llega a ``minimum``.
    """
    row = db.execute(
        select(Project, ProjectMember.role)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(Project.id == project_id, ProjectMember.user_id == user.id)
    ).first()
    if row is None:
        raise ProjectNotFoundError()
    membership = Membership(project=row[0], role=_role(row[1]))
    if not membership.can(minimum):
        raise ProjectForbiddenError()
    return membership


def list_projects(db: Session, user: User, *, q: str | None, limit: int, offset: int) -> tuple[list[Membership], int]:
    """Proyectos de los que ``user`` es miembro, por nombre."""
    query = (
        select(Project, ProjectMember.role)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user.id)
    )
    if q:
        pattern = f"%{q.strip().lower()}%"
        query = query.where(or_(func.lower(Project.name).like(pattern), func.lower(Project.description).like(pattern)))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(query.order_by(func.lower(Project.name), Project.id).limit(limit).offset(offset)).all()
    return [Membership(project=p, role=_role(r)) for p, r in rows], total


def _check_name(db: Session, owner_id: int, name: str, exclude_id: int | None = None) -> str:
    name = name.strip()
    query = select(Project.id).where(Project.owner_id == owner_id, func.lower(Project.name) == name.lower())
    if exclude_id is not None:
        query = query.where(Project.id != exclude_id)
    if db.scalar(query) is not None:
        raise ProjectNameTakenError()
    return name


def create_project(db: Session, user: User, *, name: str, description: str, ctx: RequestContext) -> Membership:
    project = Project(owner_id=user.id, name=_check_name(db, user.id, name), description=description.strip())
    db.add(project)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner"))
    audit.record(
        db, action=AuditAction.PROJECT_CREATE, ctx=ctx, actor_id=user.id, target_type="project",
        target_id=project.id, details={"name": project.name},
    )  # fmt: skip
    db.commit()
    return Membership(project=project, role="owner")


def update_project(
    db: Session, user: User, membership: Membership, *, name: str | None, description: str | None, ctx: RequestContext
) -> Membership:
    project = membership.project
    changed = []
    if name is not None and name.strip() != project.name:
        project.name = _check_name(db, project.owner_id, name, exclude_id=project.id)
        changed.append("name")
    if description is not None and description.strip() != project.description:
        project.description = description.strip()
        changed.append("description")
    if changed:
        audit.record(
            db, action=AuditAction.PROJECT_UPDATE, ctx=ctx, actor_id=user.id, target_type="project",
            target_id=project.id, details={"fields": changed},
        )  # fmt: skip
    db.commit()
    return membership


def delete_project(db: Session, user: User, membership: Membership, *, settings: Settings, ctx: RequestContext) -> None:
    """Borra el proyecto, sus ejecuciones y su carpeta del workspace.

    Raises:
        ProjectBusyError: Hay ejecuciones en cola o en curso.
    """
    project = membership.project
    busy = db.scalar(select(func.count()).where(Run.project_id == project.id, Run.status.in_(("queued", "running"))))
    if busy:
        raise ProjectBusyError("Cancela o espera a que terminen antes de borrar el proyecto.")
    folder = project_folder(settings.workspace_dir, project)
    audit.record(
        db, action=AuditAction.PROJECT_DELETE, ctx=ctx, actor_id=user.id, target_type="project",
        target_id=project.id, details={"name": project.name},
    )  # fmt: skip
    db.delete(project)
    db.commit()
    if folder is not None:
        remove_tree(folder)


def project_folder(workspace_dir: Path, project: Project) -> Path | None:
    """Carpeta del proyecto en el workspace (solo IDs)."""
    try:
        return safe_path(workspace_dir, f"users/{int(project.owner_id)}/projects/{int(project.id)}")
    except ValueError:
        return None


# --- miembros ----------------------------------------------------------------------------------------------------


def list_members(db: Session, project: Project) -> list[ProjectMember]:
    return list(
        db.scalars(
            select(ProjectMember).where(ProjectMember.project_id == project.id).order_by(ProjectMember.added_at)
        ).all()
    )


def _owners(db: Session, project_id: int) -> int:
    return (
        db.scalar(select(func.count()).where(ProjectMember.project_id == project_id, ProjectMember.role == "owner"))
        or 0
    )


def add_member(
    db: Session, actor: User, project: Project, *, username: str, role: ProjectRole, ctx: RequestContext
) -> ProjectMember:
    """Añade un usuario activo como miembro.

    Raises:
        MemberNotFoundError: El usuario no existe o está desactivado.
        MemberExistsError: Ya es miembro.
    """
    user = get_by_username(db, username)
    if user is None or not user.is_active:
        raise MemberNotFoundError("No hay ningún usuario activo con ese nombre.")
    if db.get(ProjectMember, (project.id, user.id)) is not None:
        raise MemberExistsError()
    member = ProjectMember(project_id=project.id, user_id=user.id, role=role)
    db.add(member)
    audit.record(
        db, action=AuditAction.PROJECT_MEMBER_ADD, ctx=ctx, actor_id=actor.id, target_type="project",
        target_id=project.id, details={"user_id": user.id, "role": role},
    )  # fmt: skip
    db.commit()
    db.refresh(member)
    return member


def _get_member(db: Session, project: Project, user_id: int) -> ProjectMember:
    member = db.get(ProjectMember, (project.id, user_id))
    if member is None:
        raise MemberNotFoundError()
    return member


def update_member(
    db: Session, actor: User, project: Project, user_id: int, *, role: ProjectRole, ctx: RequestContext
) -> ProjectMember:
    """Cambia el rol de un miembro.

    Raises:
        MemberNotFoundError, LastOwnerError.
    """
    member = _get_member(db, project, user_id)
    if member.role == "owner" and role != "owner" and _owners(db, project.id) <= 1:
        raise LastOwnerError()
    member.role = role
    audit.record(
        db, action=AuditAction.PROJECT_MEMBER_UPDATE, ctx=ctx, actor_id=actor.id, target_type="project",
        target_id=project.id, details={"user_id": user_id, "role": role},
    )  # fmt: skip
    db.commit()
    return member


def remove_member(db: Session, actor: User, membership: Membership, user_id: int, *, ctx: RequestContext) -> None:
    """Quita a un miembro. Un owner quita a cualquiera; cualquier miembro puede salir por sí mismo.

    Raises:
        ProjectForbiddenError, MemberNotFoundError, LastOwnerError.
    """
    project = membership.project
    if user_id != actor.id and not membership.can("owner"):
        raise ProjectForbiddenError()
    member = _get_member(db, project, user_id)
    if member.role == "owner" and _owners(db, project.id) <= 1:
        raise LastOwnerError()
    audit.record(
        db, action=AuditAction.PROJECT_MEMBER_REMOVE, ctx=ctx, actor_id=actor.id, target_type="project",
        target_id=project.id, details={"user_id": user_id},
    )  # fmt: skip
    db.delete(member)
    db.commit()


# --- conexiones del proyecto -------------------------------------------------------------------------------------


def list_project_connections(db: Session, project: Project) -> list[ProjectConnection]:
    return list(
        db.scalars(
            select(ProjectConnection)
            .where(ProjectConnection.project_id == project.id)
            .order_by(ProjectConnection.alias)
        ).all()
    )


def get_project_connection(db: Session, project: Project, alias: str) -> ProjectConnection:
    """Conexión del proyecto por alias.

    Raises:
        ProjectConnectionNotFoundError: No existe.
    """
    link = db.scalar(
        select(ProjectConnection).where(ProjectConnection.project_id == project.id, ProjectConnection.alias == alias)
    )
    if link is None:
        raise ProjectConnectionNotFoundError(f"El proyecto no tiene ninguna conexión con el alias «{alias}».")
    return link


def add_project_connection(
    db: Session, actor: User, project: Project, *, connection_id: int, alias: str, ctx: RequestContext
) -> ProjectConnection:
    """Asocia una conexión que ``actor`` puede ver (propia o compartida).

    Al asociar una conexión privada, su propietario permite que los miembros del proyecto la usen en ejecuciones,
    nunca ver su contraseña.

    Raises:
        ConnectionNotFoundError: La conexión no es visible para ``actor``.
        AliasTakenError: El alias ya existe en el proyecto.
    """
    connection = get_visible_connection(db, actor, connection_id)
    alias = alias.strip().lower()
    exists = db.scalar(
        select(ProjectConnection.id).where(ProjectConnection.project_id == project.id, ProjectConnection.alias == alias)
    )
    if exists is not None:
        raise AliasTakenError()
    link = ProjectConnection(project_id=project.id, connection_id=connection.id, alias=alias, added_by=actor.id)
    db.add(link)
    audit.record(
        db, action=AuditAction.PROJECT_CONNECTION_ADD, ctx=ctx, actor_id=actor.id, target_type="project",
        target_id=project.id, details={"alias": alias, "connection_id": connection.id},
    )  # fmt: skip
    db.commit()
    db.refresh(link)
    return link


def remove_project_connection(db: Session, actor: User, project: Project, alias: str, *, ctx: RequestContext) -> None:
    link = get_project_connection(db, project, alias)
    audit.record(
        db, action=AuditAction.PROJECT_CONNECTION_REMOVE, ctx=ctx, actor_id=actor.id, target_type="project",
        target_id=project.id, details={"alias": alias},
    )  # fmt: skip
    db.delete(link)
    db.commit()
