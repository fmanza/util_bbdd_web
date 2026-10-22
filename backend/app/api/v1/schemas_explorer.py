"""Esquemas HTTP del explorador de metadatos, las queries nombradas y el SQL libre (Fase 4)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

ObjectKind = Literal["table", "view", "routine"]
Identifier = Annotated[str, Field(min_length=1, max_length=128)]
Cell = str | int | float | bool | None


class _Loose(BaseModel):
    """Modelos de util_bbdd: se ignoran los campos que la librería añada en versiones futuras."""

    model_config = ConfigDict(extra="ignore")


class SchemaItem(BaseModel):
    name: str
    system: bool
    cached: bool


class SchemaList(BaseModel):
    default: str | None
    schemas: list[SchemaItem]


class TableItem(BaseModel):
    name: str
    comment: str | None
    columns: int


class ViewItem(BaseModel):
    name: str
    comment: str | None
    materialized: bool


class RoutineItem(BaseModel):
    name: str
    routine_type: str | None
    signature: str
    return_type: str | None


class DatabaseInfo(_Loose):
    version: str | None = None
    charset: str | None = None
    collation: str | None = None


class SchemaSummary(BaseModel):
    """Árbol de un schema leído del snapshot (cacheado)."""

    engine: str | None
    schema_name: str
    database: DatabaseInfo | None
    fetched_at: datetime
    size_bytes: int
    tables: list[TableItem]
    views: list[ViewItem]
    routines: list[RoutineItem]


class ColumnOut(_Loose):
    name: str
    ordinal: int
    data_type: str
    nullable: bool
    length: int | None = None
    precision: int | None = None
    scale: int | None = None
    default: str | None = None
    comment: str | None = None
    identity: str | None = None
    generated: str | None = None


class KeyOut(_Loose):
    name: str
    columns: list[str]


class CheckOut(_Loose):
    name: str
    expression: str


class IndexOut(_Loose):
    name: str
    columns: list[str]
    unique: bool
    primary: bool = False
    method: str | None = None
    predicate: str | None = None


class ForeignKeyOut(_Loose):
    table: str
    name: str
    columns: list[str]
    ref_schema: str
    ref_table: str
    ref_columns: list[str]
    on_delete: str
    on_update: str


class TableDetail(BaseModel):
    """Detalle de una tabla: columnas, claves, índices y FK salientes y entrantes."""

    name: str
    comment: str | None
    fetched_at: datetime
    columns: list[ColumnOut]
    primary_key: KeyOut | None
    uniques: list[KeyOut]
    checks: list[CheckOut]
    indexes: list[IndexOut]
    foreign_keys: list[ForeignKeyOut]
    referenced_by: list[ForeignKeyOut]


class DdlOut(BaseModel):
    kind: ObjectKind
    name: str
    ddl: str


class QueryResultOut(BaseModel):
    """Resultado de una consulta: como mucho ``limit`` filas; ``truncated`` si había más."""

    columns: list[str]
    rows: list[list[Cell]]
    truncated: bool
    row_count: int
    duration_ms: int


class FreeSqlIn(BaseModel):
    sql: Annotated[str, Field(min_length=1, max_length=100_000)]
    limit: Annotated[int | None, Field(ge=1, le=10_000)] = None


class SqlConnection(BaseModel):
    alias: str
    connection_name: str
    db_type: str
    read_only: bool
    supported: bool
    read_only_transaction: bool


class SqlCapabilities(BaseModel):
    """Si el usuario puede usar SQL libre en el proyecto y con qué conexiones."""

    allowed: bool
    reason: str | None
    connections: list[SqlConnection]


class NamedQueryRun(BaseModel):
    params: dict[str, str | int | float] = Field(default_factory=dict)
    limit: Annotated[int | None, Field(ge=1, le=10_000)] = None


class NamedQueryOut(BaseModel):
    id: int
    db_type: str
    name: str
    description: str
    params: list[str]
    sql_template: str
    created_at: datetime
    updated_at: datetime


class NamedQueryCreate(BaseModel):
    db_type: Annotated[str, Field(min_length=1, max_length=32)]
    name: Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")]
    description: Annotated[str, Field(max_length=500)] = ""
    sql_template: Annotated[str, Field(min_length=1, max_length=20_000)]


class NamedQueryUpdate(BaseModel):
    name: Annotated[str | None, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")] = None
    description: Annotated[str | None, Field(max_length=500)] = None
    sql_template: Annotated[str | None, Field(min_length=1, max_length=20_000)] = None
