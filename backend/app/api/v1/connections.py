"""``/api/v1/connections``: conexiones del usuario y compartidas, prueba y readiness (ADR-004)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from app.api.deps import Context, CurrentUser, DbSession, SettingsDep
from app.api.v1.schemas import (
    MAX_PAGE_SIZE,
    ConnectionCreate,
    ConnectionOut,
    ConnectionPage,
    ConnectionTestOut,
    ConnectionUpdate,
    ProbeErrorOut,
    ReadinessFindingOut,
    ReadinessOut,
)
from app.db.models import Connection, User
from app.domain.connections import service
from app.domain.connections.service import ERROR_MESSAGES, ConnectionData

router = APIRouter(prefix="/connections", tags=["connections"])

_401: dict[int | str, dict[str, Any]] = {401: {"description": "No autenticado"}}
_404: dict[int | str, dict[str, Any]] = {404: {"description": "No existe o no es visible"}}
_403: dict[int | str, dict[str, Any]] = {
    403: {"description": "Conexión compartida ajena, visibilidad shared sin ser admin o CSRF no válido"}
}
_WRITE: dict[int | str, dict[str, Any]] = {
    **_401,
    **_403,
    409: {"description": "Ya existe una conexión con ese nombre"},
    422: {"description": "Parámetros no válidos para el motor"},
}
_PROBE: dict[int | str, dict[str, Any]] = {**_401, **_404, 429: {"description": "Demasiadas pruebas en curso"}}


def _out(connection: Connection, user: User) -> ConnectionOut:
    return ConnectionOut(
        id=connection.id,
        name=connection.name,
        db_type=connection.db_type,
        description=connection.description,
        params=connection.params,
        has_password=connection.secret_enc is not None,
        read_only=connection.read_only,
        visibility="shared" if connection.visibility == "shared" else "private",
        owner_id=connection.owner_id,
        owner_username=connection.owner.username,
        editable=service.can_edit(user, connection),
        last_test_at=connection.last_test_at,
        last_test_ok=connection.last_test_ok,
        last_test_error=connection.last_test_error,
        created_at=connection.created_at,
        updated_at=connection.updated_at,
    )


def _error(code: str | None) -> ProbeErrorOut | None:
    if code is None:
        return None
    return ProbeErrorOut(code=code, message=ERROR_MESSAGES.get(code, ERROR_MESSAGES["unknown"]))


@router.get("", response_model=ConnectionPage, summary="Listar conexiones", responses=_401)
def list_connections(
    user: CurrentUser,
    db: DbSession,
    db_type: Annotated[str | None, Query(max_length=32)] = None,
    q: Annotated[str | None, Query(max_length=100, description="Texto en nombre o descripción")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ConnectionPage:
    """Conexiones propias y compartidas."""
    rows, total = service.list_connections(db, user, db_type=db_type, q=q, limit=limit, offset=offset)
    return ConnectionPage(items=[_out(c, user) for c in rows], total=total)


@router.post(
    "",
    response_model=ConnectionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear conexión",
    responses={**_WRITE, 404: {"description": "Motor no soportado"}},
)
def create_connection(
    body: ConnectionCreate, user: CurrentUser, db: DbSession, settings: SettingsDep, ctx: Context
) -> ConnectionOut:
    """Crea una conexión; la contraseña se guarda cifrada."""
    data = ConnectionData(
        name=body.name,
        db_type=body.db_type,
        description=body.description,
        params=body.params,
        password=body.password.get_secret_value() if body.password else None,
        read_only=body.read_only,
        visibility=body.visibility,
    )
    return _out(service.create_connection(db, user, data, settings=settings, ctx=ctx), user)


@router.get("/{connection_id}", response_model=ConnectionOut, summary="Ver conexión", responses={**_401, **_404})
def get_connection(connection_id: int, user: CurrentUser, db: DbSession) -> ConnectionOut:
    """Detalle de una conexión visible (nunca incluye la contraseña)."""
    return _out(service.get_visible(db, user, connection_id), user)


@router.patch("/{connection_id}", response_model=ConnectionOut, summary="Editar conexión", responses={**_WRITE, **_404})
def update_connection(
    connection_id: int, body: ConnectionUpdate, user: CurrentUser, db: DbSession, settings: SettingsDep, ctx: Context
) -> ConnectionOut:
    """Edita nombre, descripción, parámetros, contraseña, solo lectura o visibilidad."""
    connection = service.get_editable(db, user, connection_id)
    data = ConnectionData(
        name=body.name,
        description=body.description,
        params=body.params,
        password=body.password.get_secret_value() if body.password else None,
        read_only=body.read_only,
        visibility=body.visibility,
    )
    return _out(service.update_connection(db, user, connection, data, settings=settings, ctx=ctx), user)


@router.delete(
    "/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar conexión",
    responses={**_401, **_403, **_404},
)
def delete_connection(connection_id: int, user: CurrentUser, db: DbSession, ctx: Context) -> None:
    """Borra una conexión propia (o compartida, si eres admin)."""
    service.delete_connection(db, user, service.get_editable(db, user, connection_id), ctx=ctx)


@router.post("/{connection_id}/test", response_model=ConnectionTestOut, summary="Probar conexión", responses=_PROBE)
def test_connection(
    connection_id: int, user: CurrentUser, db: DbSession, settings: SettingsDep, ctx: Context
) -> ConnectionTestOut:
    """Conecta en un subproceso con timeout. El error es un código estable con un mensaje sin datos del driver."""
    connection = service.get_visible(db, user, connection_id)
    outcome = service.run_test(db, user, connection, settings=settings, ctx=ctx)
    return ConnectionTestOut(
        ok=outcome.ok,
        duration_ms=outcome.duration_ms,
        server_version=outcome.server_version,
        tested_at=outcome.tested_at,
        error=_error(outcome.error_code),
    )


@router.get("/{connection_id}/readiness", response_model=ReadinessOut, summary="Readiness del motor", responses=_PROBE)
def readiness(
    connection_id: int, user: CurrentUser, db: DbSession, settings: SettingsDep, ctx: Context
) -> ReadinessOut:
    """Condiciones de ejecución del motor (``EngineReadinessAdvisor`` de util_bbdd) sobre esta conexión."""
    connection = service.get_visible(db, user, connection_id)
    outcome = service.readiness(db, user, connection, settings=settings, ctx=ctx)
    report = outcome.report
    return ReadinessOut(
        supported=report.supported if report else False,
        dynamic=report.dynamic if report else False,
        detail=report.detail if report else None,
        checked_at=report.checked_at if report else None,
        findings=[
            ReadinessFindingOut(level=f.level, param=f.param, current=f.current, recommendation=f.recommendation)
            for f in (report.findings if report else ())
        ],
        error=_error(outcome.error_code),
    )
