"""Esquemas HTTP de la migración DDL (Fase 7): plan guardado e informe del modo seco o de la aplicación."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Plan(BaseModel):
    # El JSON guardado puede traer campos de versiones posteriores: se ignoran.
    model_config = ConfigDict(extra="ignore")


class PlanWarningOut(_Plan):
    table: str
    column: str | None = None
    category: str
    target_type: str = ""
    message: str
    severity: Literal["INFO", "WARNING", "ERROR"]
    source_type: str | None = None
    proposals: list[str] = []
    code: str | None = None


class PlanColumnOut(_Plan):
    name: str
    original_name: str
    source_type: str
    target_type: str
    nullable: bool
    default: str | None = None
    auto_increment: bool = False
    omit: bool = False


class PlanIndexOut(_Plan):
    name: str
    columns: list[str]
    unique: bool


class PlanForeignKeyOut(_Plan):
    name: str
    columns: list[str]
    ref_table: str
    ref_columns: list[str] = []


class FkMismatchOut(_Plan):
    """FK entre columnas de tipos distintos en el destino (GAPS G28)."""

    table: str
    foreign_key: str
    column: str
    column_type: str
    ref_table: str
    ref_column: str
    ref_type: str


class PlanTableOut(_Plan):
    name: str
    original_name: str
    comment: str = ""
    primary_key: list[str] = []
    columns: list[PlanColumnOut] = []
    indexes: list[PlanIndexOut] = []
    foreign_keys: list[PlanForeignKeyOut] = []


class PlanObjectOut(_Plan):
    name: str
    original_name: str | None = None
    routine_type: str | None = None


class MigrationPlanOut(_Plan):
    """Plan de migración guardado por ``migrate_plan``."""

    source_engine: str
    target_engine: str
    source_schema: str
    error_count: int
    warning_count: int
    info_count: int
    statements_hash: str
    statements: list[str]
    warnings: list[PlanWarningOut] = []
    tables: list[PlanTableOut] = []
    views: list[PlanObjectOut] = []
    routines: list[PlanObjectOut] = []
    fk_mismatches: list[FkMismatchOut] = []
    fk_blocking: bool = Field(default=False, description="El destino (MariaDB/MySQL) rechazará esas FK: no se aplica")


class ViewValidationOut(_Plan):
    view: str
    valid: bool | None = None
    method: str = ""
    error: str | None = None


class MigrationReportOut(_Plan):
    """Resultado de ``migrate_apply`` (modo seco o aplicación)."""

    mode: Literal["dry_run", "apply"]
    statements_hash: str
    statements: int
    conflicts: list[str] = []
    views: list[ViewValidationOut] = []
    fk_mismatches: list[FkMismatchOut] = []
    fk_blocking: bool = False
    applied: int = 0
    failed_position: int | None = None
    failed_statement: str | None = None
    error: str | None = Field(default=None, description="Mensaje del motor recortado")
