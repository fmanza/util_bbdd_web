"""``/api/v1/admin/storage``: cuota, retención y purga por cuota administrables (solo ``admin``, ADR-012)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, Context, DbSession, SettingsDep
from app.api.v1.schemas_storage import PurgePreviewOut, StorageSettingsOut, StorageUpdate, UsageOut, UsagePage
from app.domain.storage import service
from app.domain.storage.service import SettingState, Usage

router = APIRouter(prefix="/admin/storage", tags=["admin"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    403: {"description": "Sin rol de administrador o CSRF no válido"},
}


def _settings_out(state: dict[str, SettingState]) -> StorageSettingsOut:
    return StorageSettingsOut.model_validate({key: vars(value) for key, value in state.items()})


def usage_out(usage: Usage) -> UsageOut:
    return UsageOut(**vars(usage), used_bytes=usage.used_bytes, used_pct=usage.used_pct)


@router.get("", response_model=StorageSettingsOut, summary="Ajustes de almacenamiento", responses=_ERRORS)
def get_storage(_: AdminUser, db: DbSession, settings: SettingsDep) -> StorageSettingsOut:
    return _settings_out(service.settings_state(db, settings))


@router.patch(
    "", response_model=StorageSettingsOut, summary="Cambiar ajustes de almacenamiento",
    responses={**_ERRORS, 422: {"description": "Valor fuera de rango"}},
)  # fmt: skip
def update_storage(
    body: StorageUpdate, admin: AdminUser, db: DbSession, settings: SettingsDep, ctx: Context
) -> StorageSettingsOut:
    """Un campo que no se envía no cambia; ``null`` vuelve al valor de su variable ``UBW_*``. Se aplica sin reiniciar:
    la cuota al momento y la retención en la siguiente pasada del worker (o con «Aplicar ahora»)."""
    return _settings_out(service.update_settings(db, admin, body.changes(), settings=settings, ctx=ctx))


@router.post(
    "/preview", response_model=PurgePreviewOut, summary="Qué se purgaría con esos ajustes",
    responses={**_ERRORS, 422: {"description": "Valor fuera de rango"}},
)  # fmt: skip
def preview_storage(body: StorageUpdate, _: AdminUser, db: DbSession, settings: SettingsDep) -> PurgePreviewOut:
    """Los ajustes actuales con los de ``body`` encima; no se borra nada."""
    return PurgePreviewOut(**vars(service.preview(db, settings, body.changes())))


@router.post(
    "/maintenance", status_code=status.HTTP_202_ACCEPTED, summary="Aplicar ahora la retención y la purga",
    responses=_ERRORS,
)  # fmt: skip
def request_maintenance(admin: AdminUser, db: DbSession, ctx: Context) -> None:
    """El worker la aplica en su siguiente ciclo (en lugar de esperar a la pasada horaria)."""
    service.request_maintenance(db, admin, ctx=ctx)


@router.get("/usage", response_model=UsagePage, summary="Espacio por usuario", responses=_ERRORS)
def storage_usage(
    _: AdminUser,
    db: DbSession,
    settings: SettingsDep,
    q: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UsagePage:
    items, total = service.usage_page(db, settings, q=q, limit=limit, offset=offset)
    return UsagePage(items=[usage_out(u) for u in items], total=total)
