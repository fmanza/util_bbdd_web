"""Explorador y SQL de solo lectura contra los contenedores bench (fuera del CI; ver ``test_bench_engines.py``)."""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import text
from util_bbdd import SyncDatabaseManager

from app.integrations.util_bbdd.catalog import build_params
from app.integrations.util_bbdd.isolated import PublicError
from app.integrations.util_bbdd.metadata import list_schemas, read_ddl, read_snapshot
from app.integrations.util_bbdd.sql import _run_read_only, run_free_sql
from tests.integration.test_bench_engines import BENCH, PASSWORD

pytestmark = pytest.mark.integration

SCHEMAS = {"postgresql": "public", "mysql": "bench", "mariadb": "bench", "sqlserver": "dbo", "oracle": "BENCH"}
PARENT, CHILD = "ubw_it_cliente", "ubw_it_pedido"
READ_ONLY_ERRORS = {
    "postgresql": "read-only transaction",
    "mysql": "read only transaction",
    "mariadb": "read only transaction",
    "oracle": "ora-01456",
}


def _ident(db_type: str, name: str) -> str:
    return name.upper() if db_type == "oracle" else name


def _params(db_type: str) -> dict[str, Any]:
    return build_params(db_type, {**BENCH[db_type], "password": PASSWORD})


def _ddl(db_type: str) -> list[str]:
    text_type = "VARCHAR2(50)" if db_type == "oracle" else "VARCHAR(50)"
    return [
        f"CREATE TABLE {PARENT} (id INT PRIMARY KEY, nombre {text_type} NOT NULL)",
        # FK a nivel de tabla: MySQL ignora ``REFERENCES`` escrito en la columna.
        f"CREATE TABLE {CHILD} (id INT PRIMARY KEY, cliente_id INT, FOREIGN KEY (cliente_id) REFERENCES {PARENT}(id))",
        f"INSERT INTO {PARENT} VALUES (1, 'ana')",
    ]


def _execute(db_type: str, statements: list[str], *, ignore_errors: bool = False) -> None:
    with SyncDatabaseManager(db_type, _params(db_type), use_pool=False) as manager:
        engine = manager.get_sqlalchemy_engine()
        with engine.begin() as connection:
            for statement in statements:
                try:
                    connection.execute(text(statement))
                except Exception:
                    if not ignore_errors:
                        raise


@pytest.fixture(params=sorted(BENCH))
def db_type(request: pytest.FixtureRequest) -> Iterator[str]:
    if not PASSWORD:
        pytest.skip("Define UTIL_BBDD_BENCH_PASSWORD para las pruebas contra los contenedores bench")
    engine: str = request.param
    drop = [f"DROP TABLE {CHILD}", f"DROP TABLE {PARENT}"]
    _execute(engine, drop, ignore_errors=True)
    _execute(engine, _ddl(engine))
    if engine == "oracle":
        # ORA-01466: una transacción READ ONLY no lee tablas creadas en los últimos segundos (granularidad del SCN).
        time.sleep(6)
    yield engine
    _execute(engine, drop, ignore_errors=True)


def test_schemas_snapshot_and_ddl(db_type: str) -> None:
    schema = SCHEMAS[db_type]
    params = _params(db_type)

    schemas = list_schemas(db_type, params, timeout=120)
    snapshot = read_snapshot(db_type, params, schema, timeout=180)
    ddl = read_ddl(db_type, params, schema, "table", _ident(db_type, PARENT), timeout=120)

    assert schemas.error is None, schemas.error
    assert schema in {s["name"] for s in schemas.value["schemas"]}
    assert snapshot.error is None, snapshot.error
    tables = {t["name"] for t in snapshot.value["tables"]}
    assert {_ident(db_type, PARENT), _ident(db_type, CHILD)} <= tables
    fks = [fk for fk in snapshot.value["foreign_keys"] if fk["table"] == _ident(db_type, CHILD)]
    assert fks and fks[0]["ref_table"] == _ident(db_type, PARENT)
    assert ddl.error is None, ddl.error
    assert PARENT.lower() in ddl.value.lower()


def test_free_select(db_type: str) -> None:
    result = run_free_sql(db_type, _params(db_type), f"SELECT nombre FROM {PARENT}", limit=10, timeout=60)

    assert result.error is None, result.error
    assert result.value["rows"] == [["ana"]]


def test_write_bypassing_the_guard_is_blocked_or_rolled_back(db_type: str) -> None:
    insert = f"INSERT INTO {PARENT} VALUES (2, 'intrusa')"
    with SyncDatabaseManager(db_type, _params(db_type), use_pool=False) as manager:
        if db_type == "sqlserver":
            # Sin transacción de solo lectura: util_bbdd la ejecuta en una transacción que deshace (W-8.2).
            _run_read_only(manager, insert, 10, 30)
        else:
            with pytest.raises(PublicError) as info:
                _run_read_only(manager, insert, 10, 30)
            assert info.value.code == "query_error"
            # El error debe ser el de la transacción de solo lectura, no otro cualquiera.
            assert READ_ONLY_ERRORS[db_type] in info.value.message.lower(), info.value.message

    count = run_free_sql(db_type, _params(db_type), f"SELECT COUNT(*) AS n FROM {PARENT}", limit=1, timeout=60)
    assert count.value["rows"] == [[1]]


def test_free_select_headers_without_rows_and_repeated(db_type: str) -> None:
    """G42 (util_bbdd 5.0.0): cabeceras con 0 filas y columnas repetidas. En Oracle, con los nombres del driver."""
    dual = " FROM dual" if db_type == "oracle" else ""
    empty = run_free_sql(
        db_type, _params(db_type), f"SELECT id, nombre FROM {PARENT} WHERE id < 0", limit=10, timeout=60
    )
    repeated = run_free_sql(db_type, _params(db_type), f"SELECT 1 AS a, 2 AS a{dual}", limit=10, timeout=60)

    assert empty.error is None, empty.error
    assert [c.lower() for c in empty.value["columns"]] == ["id", "nombre"] and empty.value["rows"] == []
    assert repeated.error is None, repeated.error
    assert [c.lower() for c in repeated.value["columns"]] == ["a", "a"] and repeated.value["rows"] == [[1, 2]]


def test_free_select_oracle_numbers_keep_precision(db_type: str) -> None:
    """G44 (util_bbdd 5.1.0): ``NUMBER`` de Oracle sin pasar por ``float``; enteros como ``int`` y ``FLOAT`` como número."""
    if db_type != "oracle":
        pytest.skip("Solo Oracle")
    sql = "SELECT CAST(12345678901234567.891 AS NUMBER(38,3)) AS big, 1.5 AS n, 7 AS i, COUNT(*) AS c FROM dual"

    result = run_free_sql(db_type, _params(db_type), sql, limit=1, timeout=60)

    assert result.error is None, result.error
    assert result.value["rows"] == [["12345678901234567.891", "1.5", 7, 1]]
    floating = run_free_sql(db_type, _params(db_type), "SELECT CAST(1.25 AS FLOAT) AS f FROM dual", limit=1, timeout=60)
    assert floating.error is None, floating.error
    assert floating.value["rows"] == [[1.25]]  # número, no texto (con el rodeo de W-8.2 salía «1.25»)
