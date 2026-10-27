"""Carga bulk (Fase 9) contra los contenedores bench, **escribiendo** en el destino (fuera del CI).

Por motor: la vista previa genera el SQL **sin tocar el destino**; insert con un rechazo aislado, update y delete con
las filas afectadas contadas por PK; errores sin valores de filas.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from app.integrations.util_bbdd.bulk import BulkOptions, Target, build_bulk_preview, run_bulk
from tests.integration.test_bench_engines import PASSWORD
from tests.integration.test_bench_explorer import CHILD, PARENT, SCHEMAS, _ddl, _execute, _params

pytestmark = pytest.mark.integration

ENGINES = ("postgresql", "mysql", "mariadb", "sqlserver", "oracle")


def _drop(engine: str) -> None:
    for name in (CHILD, PARENT):
        try:
            _execute(engine, [f"DROP TABLE {name}"], ignore_errors=True)
        except Exception:  # noqa: S110 (no existe; SQL Server falla también en el COMMIT)
            pass


def _count(engine: str) -> int:
    from sqlalchemy import text
    from util_bbdd import SyncDatabaseManager

    with SyncDatabaseManager(engine, _params(engine), use_pool=False) as manager:
        with manager.get_sqlalchemy_engine().connect() as connection:
            return int(connection.execute(text(f"SELECT COUNT(*) FROM {PARENT}")).scalar_one())  # noqa: S608


@pytest.fixture(params=ENGINES)
def engine(request: pytest.FixtureRequest) -> Iterator[str]:
    if not PASSWORD:
        pytest.skip("Define UTIL_BBDD_BENCH_PASSWORD para las pruebas contra los contenedores bench")
    name: str = request.param
    _drop(name)
    _execute(name, _ddl(name))  # PARENT (id, nombre NOT NULL) con la fila 1 'ana'
    yield name
    _drop(name)


def _run(engine: str, frame: pd.DataFrame, options: BulkOptions, tmp: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    target = Target(engine, _params(engine), SCHEMAS[engine])
    preview = build_bulk_preview(target, frame, options, outputs_dir=tmp / "out", work_dir=tmp / "work")
    before_apply = _count(engine)
    result = run_bulk(target, frame, options, expected_structure=preview["structure_hash"], outputs_dir=tmp / "apply")
    preview["count_after_preview"] = before_apply
    return preview, result


def test_insert_update_delete(engine: str, tmp_path: Path) -> None:
    inserts = pd.DataFrame({"ID": [2, 3, 4], "NOMBRE": ["eva", None, "o'brien"]})
    preview, result = _run(engine, inserts, BulkOptions(table=PARENT, operation="insert", on_error="isolate"),
                           tmp_path / "i")  # fmt: skip

    assert preview["errors"] == [] and preview["sql_file"]
    assert preview["count_after_preview"] == 1  # el modo seco no escribe
    sql = (tmp_path / "i" / "out" / preview["sql_file"]).read_text(encoding="utf-8")
    assert "o''brien" in sql
    assert (result["error"], result["rejected"], result["target_rows_after"]) == (None, 1, 3), result
    assert (result["committed"], result["verified"]) == (3, None), result  # G37: la apartada cuenta como enviada

    updates = pd.DataFrame({"id": [1, 2, 99], "nombre": ["ANA", "EVA", "nadie"]})
    preview, result = _run(engine, updates, BulkOptions(table=PARENT, operation="update"), tmp_path / "u")
    assert preview["matches"] == 2 and result["error"] is None and result["matches"] == 2
    assert (result["committed"], result["verified"]) == (3, True), result

    deletes = pd.DataFrame({"id": [2, 98]})
    preview, result = _run(engine, deletes, BulkOptions(table=PARENT, operation="delete"), tmp_path / "d")
    assert preview["matches"] == 1
    assert (result["target_rows_before"], result["target_rows_after"]) == (3, 2), result
    assert (result["committed"], result["verified"]) == (2, True), result


def test_failure_message_hides_the_row_values(engine: str, tmp_path: Path) -> None:
    duplicate = pd.DataFrame({"id": [1], "nombre": ["secreto"]})
    _, result = _run(engine, duplicate, BulkOptions(table=PARENT, operation="insert"), tmp_path)

    assert result["error"] is not None, result
    assert "secreto" not in result["error"] and "[SQL" not in result["error"], result["error"]
    assert result["target_rows_after"] == 1
    assert (result["committed"], result["verified"]) == (0, None), result  # atómica y fallida: no suma
