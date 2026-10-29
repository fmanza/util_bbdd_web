"""Guardián de solo lectura (``sqlglot``), plantillas de queries nombradas y serialización de celdas."""

from __future__ import annotations

import datetime as dt
import decimal
import uuid

import pytest

from app.integrations.util_bbdd.sql import (
    MAX_CELL_CHARS,
    PARAM_VALUE,
    ReadOnlyViolation,
    _engine_message,
    check_read_only,
    check_template,
    template_params,
    to_cell,
)

ENGINES = ["postgresql", "mysql", "mariadb", "oracle", "sqlserver", "sqlite"]

ALLOWED = [
    "SELECT 1",
    "select * from t where a = 'DROP TABLE x'",
    "SELECT a FROM t UNION SELECT b FROM u",
    "WITH c AS (SELECT 1 AS x) SELECT x FROM c",
    "SELECT * FROM t /* ; DELETE FROM t */",
    "SELECT count(*) FROM t GROUP BY a HAVING count(*) > 1 ORDER BY 1",
    "(SELECT 1)",
]

REJECTED = [
    "INSERT INTO t VALUES (1)",
    "UPDATE t SET a = 1",
    "DELETE FROM t",
    "DROP TABLE t",
    "CREATE TABLE x (a INT)",
    "ALTER TABLE t ADD c INT",
    "TRUNCATE TABLE t",
    "SELECT 1; DROP TABLE t",
    "SELECT 1; SELECT 2",
    "GRANT SELECT ON t TO u",
    "",
    "   ",
]


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("sql", ALLOWED)
def test_read_queries_are_allowed(engine: str, sql: str) -> None:
    check_read_only(sql, engine)


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("sql", REJECTED)
def test_writes_and_multiple_statements_are_rejected(engine: str, sql: str) -> None:
    with pytest.raises(ReadOnlyViolation):
        check_read_only(sql, engine)


@pytest.mark.parametrize(
    ("engine", "sql"),
    [
        ("postgresql", "WITH a AS (DELETE FROM t RETURNING *) SELECT * FROM a"),
        ("postgresql", "SELECT * FROM t FOR UPDATE"),
        ("postgresql", "COPY t TO STDOUT"),
        ("postgresql", "SET search_path TO x"),
        ("postgresql", "SELECT * INTO nueva FROM t"),
        ("sqlserver", "SELECT * INTO nueva FROM t"),
        ("sqlserver", "EXEC sp_who"),
        ("mysql", "SELECT * FROM t LOCK IN SHARE MODE"),
        ("mysql", "LOAD DATA INFILE 'x' INTO TABLE t"),
        ("oracle", "MERGE INTO t USING s ON (t.id = s.id) WHEN MATCHED THEN UPDATE SET t.a = s.a"),
        ("sqlite", "PRAGMA writable_schema = 1"),
        ("sqlite", "ATTACH DATABASE '/data/config.db' AS c"),
        ("postgresql", "BEGIN"),
        ("postgresql", "COMMIT"),
    ],
)
def test_evasions_are_rejected(engine: str, sql: str) -> None:
    with pytest.raises(ReadOnlyViolation):
        check_read_only(sql, engine)


def test_hsqldb_has_no_free_sql() -> None:
    with pytest.raises(ReadOnlyViolation, match="no está disponible"):
        check_read_only("SELECT 1", "hsqldb")


def test_template_params_and_validation() -> None:
    assert template_params("SELECT * FROM {schema}.{tabla} WHERE id > {min} AND x = {tabla}") == [
        "schema",
        "tabla",
        "min",
    ]
    assert check_template("SELECT COUNT(*) FROM {tabla}", "postgresql") == ["tabla"]
    with pytest.raises(ValueError):
        template_params("SELECT {0}")
    with pytest.raises(ValueError):
        template_params("SELECT {a.b}")
    with pytest.raises(ValueError):
        template_params("SELECT {")
    with pytest.raises(ReadOnlyViolation):
        check_template("DELETE FROM {tabla}", "postgresql")


@pytest.mark.parametrize("value", ["tabla", "esquema_1", "HR$EMP", "42", "-3.5", "_x"])
def test_param_values_allowed(value: str) -> None:
    assert PARAM_VALUE.fullmatch(value)


@pytest.mark.parametrize("value", ["a b", "x;y", "1 OR 1=1", "'x'", "t--", "a.b", "", "1e5", "/*"])
def test_param_values_rejected(value: str) -> None:
    assert not PARAM_VALUE.fullmatch(value)


def test_cells_are_json_safe_and_truncated() -> None:
    assert to_cell(decimal.Decimal("10.50")) == "10.50"
    assert to_cell(dt.date(2026, 10, 22)) == "2026-10-22"
    assert to_cell(dt.datetime(2026, 10, 22, 8, 0, tzinfo=dt.UTC)) == "2026-10-22T08:00:00+00:00"
    assert to_cell(uuid.UUID(int=1)) == "00000000-0000-0000-0000-000000000001"
    assert to_cell(b"\x01\xff") == "0x01ff"
    assert to_cell(float("nan")) == "nan"
    assert to_cell(None) is None and to_cell(True) is True and to_cell(3) == 3
    long = to_cell("x" * (MAX_CELL_CHARS + 10))
    assert isinstance(long, str) and len(long) == MAX_CELL_CHARS + 1


def test_engine_message_drops_urls_and_sql() -> None:
    class Orig(Exception):
        pass

    exc = Exception("ignored")
    exc.orig = Orig(  # type: ignore[attr-defined]
        'relation "x" does not exist postgresql://u:secreta@h/db\nLINE 1: SELECT * FROM x'
    )

    message = _engine_message(exc)

    assert "secreta" not in message
    assert message.startswith('relation "x" does not exist')
    assert "LINE 1" not in message


def test_run_read_only_uses_execute_custom_result(tmp_path: object) -> None:
    """Contrato G42 (util_bbdd 5.0.0, W-8.2): ``execute_custom_result`` da las cabeceras también sin filas y con nombres
    repetidos, ``max_rows`` corta y ``read_only`` bloquea las escrituras aunque se salte el guardián."""
    import sqlite3
    from pathlib import Path

    from util_bbdd import SyncDatabaseManager

    from app.integrations.util_bbdd.catalog import build_params
    from app.integrations.util_bbdd.isolated import PublicError
    from app.integrations.util_bbdd.sql import _run_read_only

    database = Path(str(tmp_path)) / "x.db"
    con = sqlite3.connect(database)
    con.executescript("CREATE TABLE t (id INTEGER, v TEXT); INSERT INTO t VALUES (1, 'a'), (2, 'b'), (3, 'c');")
    con.close()

    with SyncDatabaseManager("sqlite", build_params("sqlite", {"database": str(database)}), use_pool=False) as manager:
        page = _run_read_only(manager, "sqlite", "SELECT id, v FROM t ORDER BY id", 2, 30)
        empty = _run_read_only(manager, "sqlite", "SELECT id, v FROM t WHERE id < 0", 10, 30)
        repeated = _run_read_only(manager, "sqlite", "SELECT 1 AS a, 2 AS a", 10, 30)
        with pytest.raises(PublicError) as info:
            _run_read_only(manager, "sqlite", "DELETE FROM t", 10, 30)

    assert page["columns"] == ["id", "v"] and page["rows"] == [[1, "a"], [2, "b"]]
    assert page["truncated"] is True and page["row_count"] == 2
    assert empty["columns"] == ["id", "v"] and empty["rows"] == [] and empty["truncated"] is False
    assert repeated["columns"] == ["a", "a"] and repeated["rows"] == [[1, 2]]
    assert info.value.code == "query_error" and "readonly" in info.value.message.lower()
    con = sqlite3.connect(database)
    try:
        assert con.execute("SELECT COUNT(*) FROM t").fetchone() == (3,)  # el motor bloqueó el DELETE (G19)
    finally:
        con.close()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (decimal.Decimal("7"), 7),
        (decimal.Decimal("1E+3"), 1000),
        (decimal.Decimal("12345678901234567.891"), decimal.Decimal("12345678901234567.891")),
        (decimal.Decimal("1.50"), decimal.Decimal("1.50")),
        (decimal.Decimal("NaN"), "NaN"),
        (2.5, 2.5),
        ("7", "7"),
    ],
)
def test_oracle_number_keeps_precision_and_integers(value: object, expected: object) -> None:
    """G44: con ``fetch_decimals`` los ``NUMBER`` de Oracle llegan como ``Decimal``; los enteros vuelven a ``int``."""
    from app.integrations.util_bbdd.sql import _oracle_number

    result = _oracle_number(value)

    assert (str(result) == expected) if expected == "NaN" else (result == expected and type(result) is type(expected))
