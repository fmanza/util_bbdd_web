"""``/api/v1/users``: administración de usuarios (permiso ``users.manage``)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from app.api.deps import Context, DbSession, SettingsDep, UserManager
from app.api.v1.schemas import (
    MAX_PAGE_SIZE,
    BlockingConnection,
    BlockingProject,
    TransferItem,
    UserCreate,
    UserDeletionCheck,
    UserOut,
    UserPage,
    UserTransfer,
    UserTransferRequest,
    UserUpdate,
)
from app.db.models import User
from app.domain.identity import roles, transfer, users
from app.domain.identity.transfer import TransferPlan
from app.domain.identity.users import UserChanges, UserSort, UserStatus
from app.domain.sorting import SortOrder

router = APIRouter(prefix="/users", tags=["users"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    403: {"description": "Sin el permiso, CSRF no válido, o el usuario tiene permisos que no tienes"},
}
_404: dict[int | str, dict[str, Any]] = {404: {"description": "No existe"}}


def _target(db: DbSession, user_id: int, actor: User) -> User:
    """Usuario sobre el que ``actor`` va a actuar: debe tener todos sus permisos (ADR-014). Sin esta regla, quien solo
    gestiona usuarios podría restablecer la contraseña de un administrador y entrar como él.

    Raises:
        UserNotFoundError: No existe (404).
        PermissionEscalationError: Tiene permisos que ``actor`` no tiene (403).
    """
    user = users.get_user(db, user_id)
    roles.check_grant(actor, user.permissions)
    return user


def _out(user: User, project_count: int) -> UserOut:
    return UserOut.model_validate(user).model_copy(update={"project_count": project_count})


def _out_db(db: DbSession, user: User) -> UserOut:
    return _out(user, users.project_count(db, user.id))


def _transfer(plan: TransferPlan) -> UserTransfer:
    def items(values: list[transfer.Item]) -> list[TransferItem]:
        return [TransferItem.model_validate(i, from_attributes=True) for i in values]

    return UserTransfer(
        can_transfer=plan.can_transfer,
        reasons=plan.reasons,
        created_projects=items(plan.created_projects),
        owned_projects=items(plan.owned_projects),
        other_memberships=items(plan.other_memberships),
        connections=items(plan.connections),
        busy_projects=items(plan.busy_projects),
    )


@router.get("", response_model=UserPage, summary="Listar usuarios", responses=_ERRORS)
def list_users(
    _: UserManager,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=64, description="Texto en usuario o nombre")] = None,
    role_id: Annotated[int | None, Query(description="Solo usuarios de este rol")] = None,
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
        db, q=q, role_id=role_id, status=status_filter, limit=limit, offset=offset, sort=sort, order=order
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
def create_user(body: UserCreate, admin: UserManager, db: DbSession, settings: SettingsDep, ctx: Context) -> UserOut:
    """Crea un usuario con la contraseña inicial, el rol, el estado y la cuota indicados. Solo se asignan roles cuyos
    permisos tiene quien da de alta."""
    role = roles.get_role(db, body.role_id) if body.role_id is not None else roles.builtin_role(db, "user")
    roles.check_grant(admin, role.permission_list)
    user = users.create_user(
        db,
        username=body.username,
        display_name=body.display_name,
        password=body.password.get_secret_value(),
        role=role,
        settings=settings,
        ctx=ctx,
        actor_id=admin.id,
        is_active=body.is_active,
        storage_quota_mb=body.storage_quota_mb,
    )
    return _out(user, 0)


@router.get("/{user_id}", response_model=UserOut, summary="Ver usuario", responses={**_ERRORS, **_404})
def get_user(user_id: int, _: UserManager, db: DbSession) -> UserOut:
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
        403: {"description": "Sin el permiso, CSRF no válido, o el rol tiene permisos que no tienes"},
        409: {"description": "Último administrador, o desactivarte o cambiar tu propio rol"},
    },
)
def update_user(
    user_id: int, body: UserUpdate, admin: UserManager, db: DbSession, settings: SettingsDep, ctx: Context
) -> UserOut:
    """Cambia nombre, rol, estado, cuota o contraseña. Cambiar el rol exige tener los permisos del actual y del nuevo;
    cambiar el rol, desactivar o restablecer la contraseña cierra sus sesiones."""
    user = _target(db, user_id, admin)
    changes = UserChanges(
        display_name=body.display_name,
        role=roles.get_role(db, body.role_id) if body.role_id is not None else None,
        is_active=body.is_active,
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
def unlock_user(user_id: int, admin: UserManager, db: DbSession, ctx: Context) -> UserOut:
    """Quita el bloqueo por intentos fallidos de inicio de sesión (se audita)."""
    user = users.unlock_user(db, users.get_user(db, user_id), actor=admin, ctx=ctx)
    return _out_db(db, user)


@router.get(
    "/{user_id}/deletion-check",
    response_model=UserDeletionCheck,
    summary="Comprobar si se puede borrar un usuario",
    responses={**_ERRORS, **_404},
)
def deletion_check(user_id: int, admin: UserManager, db: DbSession) -> UserDeletionCheck:
    """Proyectos (como miembro o creador) y conexiones que impiden borrarlo, o si es el propio admin o el último."""
    check = users.deletion_check(db, _target(db, user_id, admin), actor=admin)
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
def delete_user(user_id: int, admin: UserManager, db: DbSession, settings: SettingsDep, ctx: Context) -> None:
    """Borra un usuario sin proyectos ni conexiones en uso (ADR-013). Se borran sus sesiones y sus conexiones privadas
    sin proyectos; la auditoría conserva su nombre."""
    users.delete_user(db, _target(db, user_id, admin), actor=admin, settings=settings, ctx=ctx)


@router.get(
    "/{user_id}/transfer-preview",
    response_model=UserTransfer,
    summary="Vista previa de transferir proyectos y conexiones",
    responses={**_ERRORS, 404: {"description": "No existe el usuario o el destino"}},
)
def transfer_preview(
    user_id: int,
    admin: UserManager,
    db: DbSession,
    target_user_id: Annotated[int, Query(description="Usuario que lo recibe")],
) -> UserTransfer:
    """Qué se movería a ``target_user_id`` (con los nombres que cambian) y qué lo impide."""
    origin = _target(db, user_id, admin)
    return _transfer(transfer.transfer_preview(db, origin, _target(db, target_user_id, admin)))


@router.post(
    "/{user_id}/transfer",
    response_model=UserTransfer,
    summary="Transferir proyectos y conexiones a otro usuario",
    responses={
        **_ERRORS,
        404: {"description": "No existe el usuario o el destino"},
        409: {"description": "Mismo usuario, destino inactivo o no admin (compartidas), o ejecuciones activas"},
    },
)
def transfer_user(
    user_id: int, body: UserTransferRequest, admin: UserManager, db: DbSession, settings: SettingsDep, ctx: Context
) -> UserTransfer:
    """Cede los proyectos que creó (su carpeta se mueve), la propiedad de los suyos y sus conexiones compartidas o
    en uso; con ``remove_memberships`` lo quita además de todos los proyectos (ADR-013)."""
    origin = _target(db, user_id, admin)
    target = _target(db, body.target_user_id, admin)
    plan = transfer.transfer_user(
        db, origin, target, actor=admin, remove_memberships=body.remove_memberships, settings=settings, ctx=ctx
    )
    return _transfer(plan)
