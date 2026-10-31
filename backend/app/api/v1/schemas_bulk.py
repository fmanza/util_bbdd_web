"""Esquemas HTTP de la carga bulk (Fase 9): vista previa (modo seco) y resultado."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Bulk(BaseModel):
    # Documentos guardados por el job: se ignoran campos de versiones posteriores.
    model_config = ConfigDict(extra="ignore")


class BulkPlanOut(_Bulk):
    workers: int
    reasons: list[str] = []
    atomic: bool | None = Field(
        default=None,
        description="La carga irá en una sola transacción (ParallelPlan.atomic); null en documentos anteriores a la 1.5.0",
    )


class BulkPreviewOut(_Bulk):
    """Validación del fichero contra la tabla, filas afectadas, plan paralelo y SQL generado (sin ejecutar)."""

    table: str
    schema_name: str | None = Field(default=None, alias="schema")
    operation: Literal["insert", "update", "delete"]
    rows: int
    columns: list[str]
    mapping: dict[str, str]
    ignored_columns: list[str] = []
    primary_key: list[str] = []
    errors: list[str] = Field(description="Errores de validación: con alguno no se puede cargar")
    matches: int | None = Field(description="Filas del destino con la misma PK (las que update/delete tocarán)")
    target_rows: int
    parallel: BulkPlanOut
    sample: list[list[str | None]]
    sql_file: str | None = Field(description="Ruta del SQL generado dentro de outputs/ (null si hay errores)")
    sql_sample_rows: int | None = Field(
        default=None, description="El SQL es de muestra: solo las primeras N filas del fichero (null = SQL completo)"
    )
    memory_warning: bool = Field(
        default=False, description="Plan paralelo con un fichero grande: la carga lo leerá entero en memoria"
    )
    upload_filename: str | None = None
    target_engine: str
    structure_hash: str
    autoincrement_pk: list[str] = Field(
        default=[], description="Columnas de la PK que asigna la BD (AUTO_INCREMENT, SERIAL, IDENTITY), se carguen o no"
    )
    identity_always: list[str] = Field(
        default=[],
        description="Columnas cargadas GENERATED ALWAYS AS IDENTITY (PostgreSQL); sin override_identity son un error "
        "de validación",
    )


class BulkPartitionOut(_Bulk):
    index: int
    rows: int
    error: str | None = None


class BulkPkSyncOut(_Bulk):
    """Ajuste del contador de una columna PK tras el insert (``BulkCrud.sync_pk_sequences``)."""

    column: str
    status: Literal["synced", "skipped", "no_rows", "unsupported", "error"]
    max_value: int | None = None
    error: str | None = Field(default=None, description="Primera línea del error del motor, sin valores")


class BulkResultOut(_Bulk):
    """Resultado de ``bulk_apply``: filas confirmadas, filas del destino antes y después, rechazos y particiones."""

    operation: Literal["insert", "update", "delete"]
    table: str
    rows: int
    committed: int | None = Field(
        default=None,
        description="Filas enviadas y confirmadas según util_bbdd (también las apartadas); null en resultados anteriores "
        "a la 1.5.0",
    )
    matches: int | None = None
    target_rows_before: int
    target_rows_after: int | None = Field(
        description="Filas del destino tras la carga; null si no se pudieron contar (p. ej. read_timeout de "
        "MariaDB/MySQL en una tabla grande): la carga quedó confirmada pero sin verificar",
    )
    verified: bool | None = Field(
        default=None,
        description="El recuento del destino antes/después cuadra con committed (false: revisar); null si no se "
        "puede comprobar (rechazos, error, particiones fallidas o resultado anterior)",
    )
    rejected: int = 0
    error: str | None = Field(default=None, description="Primera línea del error del motor, sin valores de filas")
    cancelled: bool = Field(
        default=False,
        description="Se canceló entre lotes: en una sola transacción la carga se deshizo entera; en paralelo quedan "
        "las particiones terminadas (committed)",
    )
    parallel: BulkPlanOut
    partitions: list[BulkPartitionOut] = []
    pk_sync: list[BulkPkSyncOut] = Field(
        default=[], description="Ajuste del contador de la PK tras un insert; vacío si no se pidió o no hubo insert"
    )
