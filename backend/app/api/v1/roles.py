"""``/api/v1/roles``: roles con permisos del catálogo (ADR-014).

Verlos: ``roles.manage`` o ``users.manage`` (para asignarlos). Crearlos, cambiarlos y borrarlos: ``roles.manage``, y
nadie da ni quita un permiso que no tiene.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from app.api.deps import Context, DbSession, RoleManager, RoleReader
from app.api.v1.schemas import PermissionOut, RoleCreate, RoleOut, RoleUpdate
from app.db.models import Role
from app.domain.identity import roles
from app.domain.identity.permissions import PERMISSION_GROUPS, PERMISSIONS

router = APIRouter(prefix="/roles", tags=["users"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    403: {"description": "Sin el permiso, CSRF no válido, o el rol tiene permisos que no tienes"},
}
_404: dict[int | str, dict[str, Any]] = {404: {"description": "No existe"}}


def _out(role: Role, users: int) -> RoleOut:
    return RoleOut(
        id=role.id,
        name=role.name,
        builtin=role.builtin,
        permissions=role.permission_list,
        user_count=users,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.get("/permissions", response_model=list[PermissionOut], summary="Catálogo de permisos", responses=_ERRORS)
def list_permissions(_: RoleReader) -> list[PermissionOut]:
    """Permisos que puede tener un rol, en el orden en que se muestran."""
    return [PermissionOut(name=p, group=PERMISSION_GROUPS[p]) for p in PERMISSIONS]


@router.get("", response_model=list[RoleOut], summary="Listar roles", responses=_ERRORS)
def list_roles(_: RoleReader, db: DbSession) -> list[RoleOut]:
    """Roles con su número de usuarios: los base primero y después por nombre."""
    return [_out(view.role, view.users) for view in roles.list_roles(db)]


@router.post(
    "",
    response_model=RoleOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear rol",
    responses={
        **_ERRORS,
        409: {"description": "Ya existe un rol con ese nombre"},
        422: {"description": "Permiso desconocido"},
    },
)
def create_role(body: RoleCreate, actor: RoleManager, db: DbSession, ctx: Context) -> RoleOut:
    """Crea un rol con permisos que tiene quien lo crea (se audita como ``role.create``)."""
    role = roles.create_role(db, name=body.name, permissions=body.permissions, actor=actor, ctx=ctx)
    return _out(role, 0)


@router.patch(
    "/{role_id}",
    response_model=RoleOut,
    summary="Editar rol",
    responses={
        **_ERRORS,
        **_404,
        409: {"description": "Nombre repetido, o es un rol base"},
        422: {"description": "Permiso desconocido"},
    },
)
def update_role(role_id: int, body: RoleUpdate, actor: RoleManager, db: DbSession, ctx: Context) -> RoleOut:
    """Renombra el rol o cambia sus permisos (los roles base no cambian). Quitar permisos cierra las sesiones
    de sus usuarios (``role.update``)."""
    role = roles.update_role(
        db, roles.get_role(db, role_id), name=body.name, permissions=body.permissions, actor=actor, ctx=ctx
    )
    return _out(role, roles.user_count(db, role.id))


@router.delete(
    "/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar rol",
    responses={**_ERRORS, **_404, 409: {"description": "Es un rol base o tiene usuarios"}},
)
def delete_role(role_id: int, actor: RoleManager, db: DbSession, ctx: Context) -> None:
    """Borra un rol personalizado sin usuarios (``role.delete``)."""
    roles.delete_role(db, roles.get_role(db, role_id), actor=actor, ctx=ctx)
