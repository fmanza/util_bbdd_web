"""Esquemas HTTP del diff de esquemas (Fase 6): espejo del ``SchemaDiff`` de util_bbdd y evolución."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DiffStatus = Literal["added", "removed", "modified"]


class _Diff(BaseModel):
    # El JSON guardado puede traer campos de versiones posteriores de util_bbdd: se ignoran.
    model_config = ConfigDict(extra="ignore")


class ColumnDiffOut(_Diff):
    column_name: str
    attribute: Literal["type", "nullable", "primary_key", "default", "existence"]
    source_value: str
    target_value: str


class IndexDiffOut(_Diff):
    index_name: str
    table_name: str
    status: DiffStatus
    source_columns: str = ""
    target_columns: str = ""
    source_unique: bool = False
    target_unique: bool = False


class ForeignKeyDiffOut(_Diff):
    fk_name: str
    table_name: str
    status: DiffStatus
    source_columns: str = ""
    target_columns: str = ""
    source_referred_table: str = ""
    target_referred_table: str = ""
    source_referred_columns: str = ""
    target_referred_columns: str = ""


class CommentDiffOut(_Diff):
    object_name: str
    column_name: str | None
    source_comment: str
    target_comment: str


class TableDiffOut(_Diff):
    table_name: str
    status: DiffStatus
    column_diffs: list[ColumnDiffOut] = []
    index_diffs: list[IndexDiffOut] = []
    fk_diffs: list[ForeignKeyDiffOut] = []
    comment_diffs: list[CommentDiffOut] = []


class ViewDiffOut(_Diff):
    view_name: str
    status: DiffStatus
    source_definition: str = ""
    target_definition: str = ""


class RoutineDiffOut(_Diff):
    routine_name: str
    routine_type: Literal["PROCEDURE", "FUNCTION"]
    status: DiffStatus
    source_definition: str = ""
    target_definition: str = ""


class SchemaDiffOut(_Diff):
    """Diferencias de ``target`` respecto a ``source`` (``added`` = solo en origen; ``removed`` = solo en destino)."""

    source_label: str
    target_label: str
    summary: str
    has_differences: bool
    total_differences: int
    total_leaf_differences: int
    table_diffs: list[TableDiffOut] = []
    view_diffs: list[ViewDiffOut] = []
    routine_diffs: list[RoutineDiffOut] = []


class DiffItemOut(BaseModel):
    """Diferencia hoja con clave estable entre comparaciones."""

    kind: Literal["table", "column", "index", "foreign_key", "comment", "view", "routine"]
    table: str | None
    name: str
    attribute: str | None
    status: DiffStatus
    source: str
    target: str


class DiffEvolutionOut(BaseModel):
    """Qué cambió entre la comparación ``baseline_id`` (anterior) y esta."""

    run_id: str
    baseline_id: str
    labels_match: bool = Field(description="Origen y destino son los mismos en las dos comparaciones")
    new: list[DiffItemOut]
    resolved: list[DiffItemOut]
    persisting: list[DiffItemOut]
