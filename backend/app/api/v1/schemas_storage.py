"""Esquemas del almacenamiento administrable (ADR-012)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.storage.settings import (
    BulkRows,
    QuotaMb,
    QuotaSource,
    RetentionDays,
    RunsPerProject,
    TargetPct,
    UncompressedMb,
    UploadDays,
    UploadMb,
)


class IntSettingOut(BaseModel):
    value: int = Field(description="Valor que se aplica")
    default: int = Field(description="Valor de la variable UBW_* (el que se usa si no se cambia aquí)")
    overridden: bool = Field(description="Un admin lo cambió desde la web")


class BoolSettingOut(BaseModel):
    value: bool
    default: bool
    overridden: bool


class StorageSettingsOut(BaseModel):
    user_quota_mb: IntSettingOut
    run_retention_days: IntSettingOut
    run_retention_per_project: IntSettingOut
    upload_retention_days: IntSettingOut
    quota_purge: BoolSettingOut
    quota_purge_target_pct: IntSettingOut
    upload_max_mb: IntSettingOut
    upload_max_uncompressed_mb: IntSettingOut
    bulk_max_rows: IntSettingOut


class StorageUpdate(BaseModel):
    """Cambio de ajustes: un campo que no se envía no cambia; ``null`` vuelve al valor de su variable ``UBW_*``."""

    model_config = ConfigDict(extra="forbid")

    user_quota_mb: QuotaMb | None = None
    run_retention_days: RetentionDays | None = None
    run_retention_per_project: RunsPerProject | None = None
    upload_retention_days: UploadDays | None = None
    quota_purge: bool | None = None
    quota_purge_target_pct: TargetPct | None = None
    upload_max_mb: UploadMb | None = None
    upload_max_uncompressed_mb: UncompressedMb | None = None
    bulk_max_rows: BulkRows | None = None

    def changes(self) -> dict[str, Any]:
        """Solo los campos enviados (``None`` incluido)."""
        return {key: getattr(self, key) for key in self.model_fields_set}


class PurgePreviewOut(BaseModel):
    """Lo que purgaría la siguiente pasada con esos ajustes (no se borra nada)."""

    runs: int
    run_bytes: int
    uploads: int
    upload_bytes: int
    users: int = Field(description="Usuarios afectados")


class UsageOut(BaseModel):
    user_id: int
    username: str
    display_name: str
    run_bytes: int
    upload_bytes: int
    used_bytes: int
    quota_bytes: int | None = Field(description="null = sin límite")
    quota_source: QuotaSource
    used_pct: float | None


class UsagePage(BaseModel):
    items: list[UsageOut]
    total: int


class MyStorageOut(BaseModel):
    """«Mi espacio»: solo cantidades del usuario de la sesión."""

    run_bytes: int
    upload_bytes: int
    used_bytes: int
    quota_bytes: int | None = Field(description="null = sin límite")
    quota_source: QuotaSource
    used_pct: float | None
    quota_purge: bool = Field(description="Al llegar a la cuota se purgan sus ejecuciones más antiguas")
    quota_purge_target_pct: int
    upload_max_mb: int = Field(description="Tamaño máximo de un fichero de carga (MB)")
