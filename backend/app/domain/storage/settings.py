"""Ajustes de almacenamiento administrables (ADR-012): cuota, retención, purga por cuota y límites de la carga.

El valor por defecto de cada ajuste es su variable ``UBW_*``; un admin puede sobrescribirlo desde la web y se guarda en
``app_settings``. Los ajustes **efectivos** son una copia de ``Settings`` con esas filas aplicadas: quien antes recibía
``Settings`` (retención, subidas, worker) recibe los efectivos sin cambiar de firma. Se leen en cada uso, así que la API
y el worker ven los cambios sin reiniciar. La cuota de un usuario sale de ``users.storage_quota_mb`` si la tiene.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AppSetting, User

logger = logging.getLogger(__name__)

MB: Final = 1024 * 1024
#: Clave interna con la que un admin pide al worker que aplique ya la retención y la purga.
MAINTENANCE_KEY: Final = "maintenance_requested_at"

QuotaMb = Annotated[int, Field(ge=0, le=10_000_000, description="MB; 0 = sin límite")]
RetentionDays = Annotated[int, Field(ge=0, le=3650, description="Días; 0 = no se purga por antigüedad")]
RunsPerProject = Annotated[int, Field(ge=0, le=100_000, description="Ejecuciones; 0 = sin máximo")]
UploadDays = Annotated[int, Field(ge=0, le=365, description="Días; 0 = no se purgan")]
TargetPct = Annotated[int, Field(ge=10, le=95, description="Porcentaje de la cuota")]
UploadMb = Annotated[int, Field(ge=1, le=2048, description="MB por fichero subido para la carga")]
UncompressedMb = Annotated[int, Field(ge=1, le=8192, description="MB descomprimidos de un .xlsx")]
BulkRows = Annotated[int, Field(ge=1, le=50_000_000, description="Filas de un fichero de carga")]
QuotaSource = Literal["global", "user", "unlimited"]


class StorageValues(BaseModel):
    """Ajustes administrables con sus rangos (los mismos que acepta la API)."""

    model_config = ConfigDict(extra="forbid")

    user_quota_mb: QuotaMb
    run_retention_days: RetentionDays
    run_retention_per_project: RunsPerProject
    upload_retention_days: UploadDays
    quota_purge: bool
    quota_purge_target_pct: TargetPct
    upload_max_mb: UploadMb
    upload_max_uncompressed_mb: UncompressedMb
    bulk_max_rows: BulkRows


STORAGE_KEYS: Final[tuple[str, ...]] = tuple(StorageValues.model_fields)
_ADAPTERS: Final[dict[str, TypeAdapter[Any]]] = {
    "user_quota_mb": TypeAdapter(QuotaMb),
    "run_retention_days": TypeAdapter(RetentionDays),
    "run_retention_per_project": TypeAdapter(RunsPerProject),
    "upload_retention_days": TypeAdapter(UploadDays),
    "quota_purge": TypeAdapter(bool),
    "quota_purge_target_pct": TypeAdapter(TargetPct),
    "upload_max_mb": TypeAdapter(UploadMb),
    "upload_max_uncompressed_mb": TypeAdapter(UncompressedMb),
    "bulk_max_rows": TypeAdapter(BulkRows),
}


def defaults(settings: Settings) -> dict[str, Any]:
    """Valores de las variables ``UBW_*`` (los que se usan si un admin no los cambia)."""
    return {key: getattr(settings, key) for key in STORAGE_KEYS}


def overrides(db: Session) -> dict[str, Any]:
    """Valores guardados por un admin, validados uno a uno con su rango; uno fuera de rango se ignora (y se avisa).

    No se validan las variables ``UBW_*``: pueden salirse de los rangos de la web y siguen valiendo.
    """
    stored: dict[str, Any] = {}
    for row in db.scalars(select(AppSetting).where(AppSetting.key.in_(STORAGE_KEYS))):
        try:
            stored[row.key] = _ADAPTERS[row.key].validate_python(row.value)
        except ValidationError:
            logger.warning("Ajuste de almacenamiento fuera de rango ignorado", extra={"key": row.key})
    return stored


def effective_settings(db: Session, settings: Settings, proposed: dict[str, Any] | None = None) -> Settings:
    """``settings`` con los ajustes de los admins aplicados (y ``proposed`` encima: ``None`` = valor por defecto)."""
    values = overrides(db)
    for key, value in (proposed or {}).items():
        if value is None:
            values.pop(key, None)
        else:
            values[key] = value
    return settings.model_copy(update=values)


def quota_mb(user: User, settings: Settings) -> int:
    """Cuota en MB de ``user`` (la suya o la global de ``settings`` efectivos); ``0`` = sin límite."""
    return user.storage_quota_mb if user.storage_quota_mb is not None else settings.user_quota_mb


def quota_bytes(user: User, settings: Settings) -> int | None:
    """Cuota en bytes de ``user``, o ``None`` si no tiene límite."""
    mb = quota_mb(user, settings)
    return mb * MB if mb else None


def quota_source(user: User, settings: Settings) -> QuotaSource:
    """De dónde sale la cuota de ``user``."""
    if not quota_mb(user, settings):
        return "unlimited"
    return "user" if user.storage_quota_mb is not None else "global"


def maintenance_requested_since(db: Session, since: datetime | None) -> bool:
    """Si un admin pidió aplicar ya el mantenimiento después de ``since``."""
    row = db.get(AppSetting, MAINTENANCE_KEY)
    if row is None or not isinstance(row.value, str):
        return False
    try:
        requested = datetime.fromisoformat(row.value)
    except ValueError:
        return False
    return since is None or requested > since
