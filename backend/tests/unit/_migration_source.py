"""Manager falso para planificar con ``MigrationPlanner`` sin base de datos (``MigrationPlan`` reales en los tests).

util_bbdd lee el catálogo con la ``metadata_source`` del manager (ADR-003 de util_bbdd): ``fake_manager`` expone una
fuente en memoria con los objetos dados. Sirve de origen (``MigrationPlanner.plan``) y de destino
(``MigrationPlan.check_target``).
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Any
from unittest.mock import MagicMock

from util_bbdd.metadata.model import (
    ALL_KINDS,
    ColumnMeta,
    ForeignKeyMeta,
    Kind,
    PrimaryKeyMeta,
    SchemaSnapshot,
    TableMeta,
    ViewMeta,
)

_KIND_OF: dict[type, Kind] = {
    TableMeta: Kind.TABLES,
    ViewMeta: Kind.VIEWS,
    ColumnMeta: Kind.COLUMNS,
    PrimaryKeyMeta: Kind.PRIMARY_KEYS,
    ForeignKeyMeta: Kind.FOREIGN_KEYS,
}


class _Source:
    def __init__(self, engine: str, objects: tuple[Any, ...]) -> None:
        self.engine = engine
        self.data: dict[Kind, list[Any]] = {}
        for obj in objects:
            self.data.setdefault(_KIND_OF[type(obj)], []).append(obj)

    def snapshot(
        self, schema: str | None = None, *, kinds: Collection[Kind] = ALL_KINDS, tables: Collection[str] | None = None
    ) -> SchemaSnapshot:
        return SchemaSnapshot(self.engine, schema or "", {k: tuple(self.data.get(k, ())) for k in kinds})

    def invalidate(self, schema: str | None = None, *, kinds: Collection[Kind] | None = None) -> None:
        return None


def fake_manager(engine: str, *objects: Any) -> MagicMock:
    manager = MagicMock()
    manager.metadata_source = _Source(engine, objects)
    return manager


def oracle_int_pk_and_fk() -> MagicMock:
    """Oracle ``INT`` (``NUMBER`` sin precisión) en la PK de CLIENTES y en la FK de PEDIDOS (GAPS G28)."""
    return fake_manager(
        "oracle",
        TableMeta("CLIENTES", None),
        ColumnMeta("CLIENTES", "ID", 1, "NUMBER", "NUMBER", scale=0, nullable=False),
        PrimaryKeyMeta("CLIENTES", "PK_CLIENTES", ("ID",)),
        TableMeta("PEDIDOS", None),
        ColumnMeta("PEDIDOS", "ID", 1, "NUMBER(10)", "NUMBER", precision=10, scale=0, nullable=False),
        ColumnMeta("PEDIDOS", "CLIENTE_ID", 2, "NUMBER", "NUMBER", scale=0, nullable=True),
        PrimaryKeyMeta("PEDIDOS", "PK_PEDIDOS", ("ID",)),
        ForeignKeyMeta("PEDIDOS", "FK_PED_CLI", ("CLIENTE_ID",), "S", "CLIENTES", ("ID",), "NO ACTION", "NO ACTION"),
    )
