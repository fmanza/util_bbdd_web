"""``/api/v1/users``: administración de usuarios (solo ``admin``)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, Context, DbSession, SettingsDep
from app.api.v1.schemas import (
    MAX_PAGE_SIZE,
    BlockingConnection,
    BlockingProject,
    Role,
    UserCreate,
    UserDeletionCheck,
    UserOut,
    UserPage,
    UserUpdate,
)
from app.db.models import User
from app.domain.identity import users
from app.domain.identity.users import UserChanges, UserSort, UserStatus
from app.domain.sorting import SortOrder

router = APIRouter(prefix="/users", tags=["users"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    403: {"description": "Sin rol de administrador o token CSRF no válido"},
}
_404: dict[int | str, dict[str, Any]] = {404: {"description": "No existe"}}


def _out(user: User, project_count: int) -> UserOut:
    return UserOut.model_validate(user).model_copy(update={"project_count": project_count})


def _out_db(db: DbSession, user: User) -> UserOut:
    return _out(user, users.project_count(db, user.id))


@router.get("", response_model=UserPage, summary="Listar usuarios", responses=_ERRORS)
def list_users(
    _: AdminUser,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=64, description="Texto en usuario o nombre")] = None,
    role: Annotated[Role | None, Query(description="Solo usuarios de este rol")] = None,
    status_filter: Annotated[
        UserStatus | None,
        Query(alias="status", description="``active`` (sin bloqueo), ``inactive`` o ``locked`` (por intentos)"),
    ] = None,
    sort: UserSort | None = None,
    order: SortOrder | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UserPage:
    """Usuarios con su número de proyectos (por nombre de usuario si no se pide otro orden)."""
    rows, total = users.list_users(
        db, q=q, role=role, status=status_filter, limit=limit, offset=offset, sort=sort, order=order
    )
    return UserPage(
        items=[_out(u, count) for u, count in rows], total=total, active_admins=users.count_active_admins(db)
    )


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear usuario",
    responses={**_ERRORS, 400: {"description": "Contraseña no válida"}, 409: {"description": "El usuario ya existe"}},
)
def create_user(body: UserCreate, admin: AdminUser, db: DbSession, settings: SettingsDep, ctx: Context) -> UserOut:
    """Crea un usuario con la contraseña inicial, el rol, el estado, los permisos y la cuota indicados."""
    user = users.create_user(
        db,
        username=body.username,
        display_name=body.display_name,
        password=body.password.get_secret_value(),
        role=body.role,
        settings=settings,
        ctx=ctx,
        actor_id=admin.id,
        is_active=body.is_active,
        can_run_sql=body.can_run_sql,
        can_apply_ddl=body.can_apply_ddl,
        can_write_data=body.can_write_data,
        storage_quota_mb=body.storage_quota_mb,
    )
    return _out(user, 0)


@router.get("/{user_id}", response_model=UserOut, summary="Ver usuario", responses={**_ERRORS, **_404})
def get_user(user_id: int, _: AdminUser, db: DbSession) -> UserOut:
    """Detalle de un usuario."""
    return _out_db(db, users.get_user(db, user_id))


@router.patch(
    "/{user_id}",
    response_model=UserOut,
    summary="Editar, desactivar o reactivar usuario",
    responses={
        **_ERRORS,
        **_404,
        400: {"description": "Contraseña no válida"},
        409: {"description": "Último administrador o autodesactivación"},
    },
)
def update_user(
    user_id: int, body: UserUpdate, admin: AdminUser, db: DbSession, settings: SettingsDep, ctx: Context
) -> UserOut:
    """Cambia nombre, rol, estado, permisos (SQL libre, aplicar DDL, escribir datos), cuota o contraseña. Desactivar o
    restablecer la contraseña cierra sus sesiones."""
    user = users.get_user(db, user_id)
    changes = UserChanges(
        display_name=body.display_name,
        role=body.role,
        is_active=body.is_active,
        can_run_sql=body.can_run_sql,
        can_apply_ddl=body.can_apply_ddl,
        can_write_data=body.can_write_data,
        storage_quota_mb=body.storage_quota_mb,
        global_storage_quota=body.global_storage_quota,
        password=body.password.get_secret_value() if body.password is not None else None,
    )
    return _out_db(db, users.update_user(db, user, changes, actor=admin, settings=settings, ctx=ctx))


@router.post(
    "/{user_id}/unlock",
    response_model=UserOut,
    summary="Desbloquear usuario",
    responses={**_ERRORS, **_404},
)
def unlock_user(user_id: int, admin: AdminUser, db: DbSession, ctx: Context) -> UserOut:
    """Quita el bloqueo por intentos fallidos de inicio de sesión (se audita)."""
    user = users.unlock_user(db, users.get_user(db, user_id), actor=admin, ctx=ctx)
    return _out_db(db, user)


@router.get(
    "/{user_id}/deletion-check",
    response_model=UserDeletionCheck,
    summary="Comprobar si se puede borrar un usuario",
    responses={**_ERRORS, **_404},
)
def deletion_check(user_id: int, admin: AdminUser, db: DbSession) -> UserDeletionCheck:
    """Proyectos (como miembro o creador) y conexiones que impiden borrarlo, o si es el propio admin o el último."""
    check = users.deletion_check(db, users.get_user(db, user_id), actor=admin)
    return UserDeletionCheck(
        can_delete=check.can_delete,
        reasons=check.reasons,
        projects=[BlockingProject.model_validate(p, from_attributes=True) for p in check.projects],
        created_projects=[BlockingProject.model_validate(p, from_attributes=True) for p in check.created_projects],
        connections=[BlockingConnection.model_validate(c, from_attributes=True) for c in check.connections],
    )


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar usuario",
    responses={
        **_ERRORS,
        **_404,
        409: {
            "description": "Es tu cuenta, el último administrador activo, o tiene proyectos o conexiones "
            "(el *problem details* lleva ``reasons``, ``projects``, ``created_projects`` y ``connections``)"
        },
    },
)
def delete_user(user_id: int, admin: AdminUser, db: DbSession, settings: SettingsDep, ctx: Context) -> None:
    """Borra un usuario sin proyectos ni conexiones en uso (ADR-013). Se borran sus sesiones y sus conexiones privadas
    sin proyectos; la auditoría conserva su nombre."""
    users.delete_user(db, users.get_user(db, user_id), actor=admin, settings=settings, ctx=ctx)
