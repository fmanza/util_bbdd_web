"""Comparación de esquemas (Fase 6) contra los contenedores bench (fuera del CI; ver ``test_bench_engines.py``).

Cada motor (con ``PARENT`` y ``CHILD``) se compara con un SQLite que solo tiene ``PARENT``; además, PostgreSQL contra
MySQL. Comprueba el schema por motor (también en minúsculas en Oracle) y que las salidas no llevan el host.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from app.integrations.util_bbdd.catalog import build_params
from app.integrations.util_bbdd.compare import CompareOptions, Side, compare_schemas
from tests.integration.test_bench_engines import BENCH, PASSWORD
from tests.integration.test_bench_explorer import CHILD, PARENT, SCHEMAS, _ddl, _execute, _params, db_type  # noqa: F401

pytestmark = pytest.mark.integration


def _sqlite_with_parent(tmp_path: Path) -> Side:
    path = tmp_path / "solo_padre.db"
    con = sqlite3.connect(path)
    con.execute(f"CREATE TABLE {PARENT} (id INT PRIMARY KEY, nombre VARCHAR(50) NOT NULL)")
    con.close()
    return Side("sqlite", build_params("sqlite", {"database": str(path)}), None, "sqlite")


def _names(items: list[dict[str, str]]) -> set[str]:
    return {t["table_name"].lower() for t in items}


def test_engine_against_sqlite(db_type: str, tmp_path: Path) -> None:  # noqa: F811
    schema = SCHEMAS[db_type].lower() if db_type == "oracle" else SCHEMAS[db_type]
    source = Side(db_type, _params(db_type), schema, "bench")
    outputs = tmp_path / "outputs"

    summary = compare_schemas(
        source,
        _sqlite_with_parent(tmp_path),
        options=CompareOptions(formats=("markdown", "sql")),
        outputs_dir=outputs,
    )

    diff = json.loads((outputs / "diff" / "schema_diff.json").read_text(encoding="utf-8"))
    added = {t["table_name"].lower() for t in diff["table_diffs"] if t["status"] == "added"}
    assert CHILD in added, summary
    assert PARENT not in added
    script = (outputs / summary["reports"]["sql"]).read_text(encoding="utf-8").lower()
    assert CHILD in script
    host = str(BENCH[db_type].get("host", ""))
    for report in summary["reports"].values():
        assert host not in (outputs / report).read_text(encoding="utf-8")


def test_postgresql_against_mysql(tmp_path: Path) -> None:
    if not PASSWORD:
        pytest.skip("Define UTIL_BBDD_BENCH_PASSWORD para las pruebas contra los contenedores bench")
    drop = [f"DROP TABLE {CHILD}", f"DROP TABLE {PARENT}"]
    for engine in ("postgresql", "mysql"):
        _execute(engine, drop, ignore_errors=True)
        _execute(engine, _ddl(engine))
    try:
        summary = compare_schemas(
            Side("postgresql", _params("postgresql"), "public", "pg"),
            Side("mysql", _params("mysql"), SCHEMAS["mysql"], "my"),
            options=CompareOptions(formats=()),
            outputs_dir=tmp_path,
        )
        diff = json.loads((tmp_path / "diff" / "schema_diff.json").read_text(encoding="utf-8"))
        assert not {PARENT, CHILD} & {
            t["table_name"].lower() for t in diff["table_diffs"] if t["status"] != "modified"
        }, summary
    finally:
        for engine in ("postgresql", "mysql"):
            _execute(engine, drop, ignore_errors=True)
