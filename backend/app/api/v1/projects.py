"""``/api/v1/projects``: proyectos, miembros y conexiones del proyecto (Fase 3)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from app.api.deps import Context, CurrentUser, DbSession, SettingsDep
from app.api.v1.schemas import MAX_PAGE_SIZE
from app.api.v1.schemas_projects import (
    MemberCreate,
    MemberOut,
    MemberUpdate,
    ProjectConnectionCreate,
    ProjectConnectionOut,
    ProjectCreate,
    ProjectOut,
    ProjectPage,
    ProjectUpdate,
)
from app.db.models import ProjectConnection, ProjectMember
from app.domain.projects import service
from app.domain.projects.service import Membership

router = APIRouter(prefix="/projects", tags=["projects"])

_401: dict[int | str, dict[str, Any]] = {401: {"description": "No autenticado"}}
_404: dict[int | str, dict[str, Any]] = {404: {"description": "No existe o no eres miembro"}}
_403: dict[int | str, dict[str, Any]] = {403: {"description": "Tu rol no lo permite o CSRF no válido"}}
_409: dict[int | str, dict[str, Any]] = {
    409: {"description": "Conflicto (nombre, último propietario, ejecuciones activas)"}
}


def _project(membership: Membership) -> ProjectOut:
    p = membership.project
    return ProjectOut(
        id=p.id,
        name=p.name,
        description=p.description,
        owner_id=p.owner_id,
        my_role=membership.role,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _member(member: ProjectMember) -> MemberOut:
    return MemberOut(
        user_id=member.user_id,
        username=member.user.username,
        display_name=member.user.display_name,
        role=member.role,
        added_at=member.added_at,
    )


def _link(link: ProjectConnection) -> ProjectConnectionOut:
    return ProjectConnectionOut(
        id=link.id,
        alias=link.alias,
        connection_id=link.connection_id,
        connection_name=link.connection.name,
        db_type=link.connection.db_type,
        read_only=link.connection.read_only,
        created_at=link.created_at,
    )


@router.get("", response_model=ProjectPage, summary="Listar mis proyectos", responses=_401)
def list_projects(
    user: CurrentUser,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProjectPage:
    """Proyectos de los que eres miembro."""
    rows, total = service.list_projects(db, user, q=q, limit=limit, offset=offset)
    return ProjectPage(items=[_project(m) for m in rows], total=total)


@router.post(
    "", response_model=ProjectOut, status_code=status.HTTP_201_CREATED, summary="Crear proyecto",
    responses={**_401, **_409},
)  # fmt: skip
def create_project(body: ProjectCreate, user: CurrentUser, db: DbSession, ctx: Context) -> ProjectOut:
    """Crea un proyecto del que eres propietario."""
    return _project(service.create_project(db, user, name=body.name, description=body.description, ctx=ctx))


@router.get("/{project_id}", response_model=ProjectOut, summary="Ver proyecto", responses={**_401, **_404})
def get_project(project_id: int, user: CurrentUser, db: DbSession) -> ProjectOut:
    return _project(service.get_membership(db, user, project_id))


@router.patch(
    "/{project_id}", response_model=ProjectOut, summary="Editar proyecto", responses={**_401, **_403, **_404, **_409}
)
def update_project(project_id: int, body: ProjectUpdate, user: CurrentUser, db: DbSession, ctx: Context) -> ProjectOut:
    """Cambia nombre o descripción (propietarios)."""
    membership = service.get_membership(db, user, project_id, "owner")
    return _project(service.update_project(db, user, membership, name=body.name, description=body.description, ctx=ctx))


@router.delete(
    "/{project_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Borrar proyecto",
    responses={**_401, **_403, **_404, **_409},
)  # fmt: skip
def delete_project(project_id: int, user: CurrentUser, db: DbSession, settings: SettingsDep, ctx: Context) -> None:
    """Borra el proyecto, sus ejecuciones y su carpeta del workspace (propietarios)."""
    membership = service.get_membership(db, user, project_id, "owner")
    service.delete_project(db, user, membership, settings=settings, ctx=ctx)


# --- miembros ----------------------------------------------------------------------------------------------------


@router.get(
    "/{project_id}/members", response_model=list[MemberOut], summary="Listar miembros", responses={**_401, **_404}
)
def list_members(project_id: int, user: CurrentUser, db: DbSession) -> list[MemberOut]:
    membership = service.get_membership(db, user, project_id)
    return [_member(m) for m in service.list_members(db, membership.project)]


@router.post(
    "/{project_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED, summary="Añadir miembro",
    responses={**_401, **_403, **_404, **_409},
)  # fmt: skip
def add_member(project_id: int, body: MemberCreate, user: CurrentUser, db: DbSession, ctx: Context) -> MemberOut:
    """Añade un usuario por su nombre de usuario (propietarios)."""
    membership = service.get_membership(db, user, project_id, "owner")
    member = service.add_member(db, user, membership.project, username=body.username, role=body.role, ctx=ctx)
    return _member(member)


@router.patch(
    "/{project_id}/members/{user_id}", response_model=MemberOut, summary="Cambiar rol",
    responses={**_401, **_403, **_404, **_409},
)  # fmt: skip
def update_member(
    project_id: int, user_id: int, body: MemberUpdate, user: CurrentUser, db: DbSession, ctx: Context
) -> MemberOut:
    membership = service.get_membership(db, user, project_id, "owner")
    return _member(service.update_member(db, user, membership.project, user_id, role=body.role, ctx=ctx))


@router.delete(
    "/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Quitar miembro o salir",
    responses={**_401, **_403, **_404, **_409},
)  # fmt: skip
def remove_member(project_id: int, user_id: int, user: CurrentUser, db: DbSession, ctx: Context) -> None:
    """Un propietario quita a cualquiera; cualquier miembro puede salir del proyecto."""
    membership = service.get_membership(db, user, project_id)
    service.remove_member(db, user, membership, user_id, ctx=ctx)


# --- conexiones del proyecto -------------------------------------------------------------------------------------


@router.get(
    "/{project_id}/connections", response_model=list[ProjectConnectionOut], summary="Conexiones del proyecto",
    responses={**_401, **_404},
)  # fmt: skip
def list_project_connections(project_id: int, user: CurrentUser, db: DbSession) -> list[ProjectConnectionOut]:
    membership = service.get_membership(db, user, project_id)
    return [_link(link) for link in service.list_project_connections(db, membership.project)]


@router.post(
    "/{project_id}/connections", response_model=ProjectConnectionOut, status_code=status.HTTP_201_CREATED,
    summary="Asociar conexión", responses={**_401, **_403, **_404, **_409},
)  # fmt: skip
def add_project_connection(
    project_id: int, body: ProjectConnectionCreate, user: CurrentUser, db: DbSession, ctx: Context
) -> ProjectConnectionOut:
    """Asocia una conexión propia o compartida con un alias (editores). Los miembros podrán usarla en ejecuciones
    sin ver su contraseña."""
    membership = service.get_membership(db, user, project_id, "editor")
    link = service.add_project_connection(
        db, user, membership.project, connection_id=body.connection_id, alias=body.alias, ctx=ctx
    )
    return _link(link)


@router.delete(
    "/{project_id}/connections/{alias}", status_code=status.HTTP_204_NO_CONTENT, summary="Quitar conexión",
    responses={**_401, **_403, **_404},
)  # fmt: skip
def remove_project_connection(project_id: int, alias: str, user: CurrentUser, db: DbSession, ctx: Context) -> None:
    membership = service.get_membership(db, user, project_id, "editor")
    service.remove_project_connection(db, user, membership.project, alias, ctx=ctx)
