"""Esquemas HTTP del volcado de datos (Fase 8): vista previa (modo seco) y resultado."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Dump(BaseModel):
    # Documentos guardados por el job: se ignoran campos de versiones posteriores.
    model_config = ConfigDict(extra="ignore")


class DumpPreviewTableOut(_Dump):
    table: str
    target_table: str | None = Field(description="Tabla del destino; null = no existe (no se cargará)")
    position: int
    in_cycle: bool
    source_rows: int
    target_rows: int | None
    skipped_columns: list[str] = Field(description="Columnas del origen que el destino no tiene (no se copian)")
    missing_target_columns: list[str] = Field(
        description="Columnas del destino obligatorias que el origen no tiene (la carga de la tabla fallará)"
    )
    outside_references: list[str] = Field(description="Tablas referenciadas por FK que no entran en el volcado")
    date_columns: list[str] = Field(
        default=[],
        description="SQLite → SQLite: columnas de fecha del destino que util_bbdd no carga desde texto (G33)",
    )


class DumpPreviewOut(_Dump):
    """Modo seco de un volcado: orden de carga por FK, ciclos, filas y avisos por tabla."""

    source_engine: str
    target_engine: str
    source_schema: str | None
    target_schema: str | None
    truncate_target: bool
    constraints_managed: bool = Field(description="util_bbdd desactiva y reactiva las constraints de este destino")
    warnings: list[str] = Field(default=[], description="Códigos de aviso: isolate_oracle (G32), sqlite_dates (G33)")
    tables: list[DumpPreviewTableOut]
    cycles: list[list[str]]
    load_order: list[str]
    structure_hash: str


class DumpTableResultOut(_Dump):
    table: str
    status: Literal["success", "missing_target", "skipped", "error"]
    source_rows: int
    target_rows_before: int
    target_rows_after: int
    rows_rejected: int = 0
    skipped_columns: list[str] = []
    position: int
    in_cycle: bool = False
    error: str | None = Field(default=None, description="Primera línea del error del motor, sin datos de filas")


class DumpConstraintOut(_Dump):
    table: str
    constraint: str
    status: Literal["enabled", "failed", "unverified"]
    error: str | None = None


class DumpPkSyncOut(_Dump):
    table: str
    status: str
    error: str | None = None


class DumpResultOut(_Dump):
    """Resultado de ``dump_apply``: por tabla, constraints reactivadas y contadores PK."""

    load_order: list[str]
    cycles: list[list[str]]
    report: bool = Field(description="Se generó el informe Excel")
    tables: list[DumpTableResultOut]
    constraints: list[DumpConstraintOut] = []
    pk_sync: list[DumpPkSyncOut] = []
    cancelled: bool = Field(
        default=False,
        description="Se canceló entre lotes: la tabla en curso se deshizo y las constraints se reactivaron; sin detalle "
        "por tabla (tables vacío)",
    )
    completed_tables: list[str] = Field(default=[], description="Tablas cargadas antes de cancelar")
