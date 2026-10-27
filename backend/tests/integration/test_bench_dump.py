"""Volcado de datos (Fase 8) contra los contenedores bench, **escribiendo** en el destino (fuera del CI).

Origen y destino con ``ubw_it_cliente``/``ubw_it_pedido`` (FK); la vista previa coincide con el orden de util_bbdd,
el volcado vacía y copia, las constraints se reactivan y, añadiendo sobre una PK repetida, el rechazo se aísla.
Las constraints que deja desactivadas un proceso muerto (con su diario) se restauran (G31).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.integrations.util_bbdd.dump import DumpOptions, Endpoint, build_preview, restore_constraints, run_dump
from tests.integration.test_bench_engines import PASSWORD
from tests.integration.test_bench_explorer import CHILD, PARENT, SCHEMAS, _ddl, _execute, _ident, _params

pytestmark = pytest.mark.integration

PAIRS = [
    ("postgresql", "mysql"),
    ("mysql", "postgresql"),
    ("oracle", "sqlserver"),
    ("mariadb", "oracle"),
    ("postgresql", "mariadb"),
]
NAMES = [CHILD, CHILD.upper(), PARENT, PARENT.upper()]


def _drop(engine: str) -> None:
    for name in NAMES:
        try:
            _execute(engine, [f"DROP TABLE {name}"], ignore_errors=True)
        except Exception:  # noqa: S110 (no existe; SQL Server falla también en el COMMIT)
            pass


def _count(engine: str, table: str) -> int:
    from sqlalchemy import text
    from util_bbdd import SyncDatabaseManager

    with SyncDatabaseManager(engine, _params(engine), use_pool=False) as manager:
        with manager.get_sqlalchemy_engine().connect() as connection:
            return int(connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one())  # noqa: S608


@pytest.fixture(params=PAIRS, ids=lambda p: f"{p[0]}-{p[1]}")
def pair(request: pytest.FixtureRequest) -> tuple[str, str]:
    if not PASSWORD:
        pytest.skip("Define UTIL_BBDD_BENCH_PASSWORD para las pruebas contra los contenedores bench")
    source, target = request.param
    for engine in (source, target):
        _drop(engine)
    _execute(source, [*_ddl(source), f"INSERT INTO {CHILD} VALUES (10, 1)", f"INSERT INTO {CHILD} VALUES (11, 1)"])
    # Destino con las mismas tablas y una fila previa en el padre (``_ddl`` inserta id=1).
    _execute(target, _ddl(target))
    yield source, target
    for engine in (source, target):
        _drop(engine)


def _endpoints(source: str, target: str) -> tuple[Endpoint, Endpoint]:
    return Endpoint(source, _params(source), SCHEMAS[source]), Endpoint(target, _params(target), SCHEMAS[target])


def test_preview_and_full_dump(pair: tuple[str, str], tmp_path: Path) -> None:
    source, target = _endpoints(*pair)
    options = DumpOptions(tables=(PARENT, CHILD), truncate_target=True)

    preview = build_preview(source, target, options)
    result = run_dump(source, target, options=options, expected_structure=preview["structure_hash"],
                      outputs_dir=tmp_path / "out", work_dir=tmp_path / "work")  # fmt: skip

    assert [t.lower() for t in preview["load_order"]] == [PARENT, CHILD]
    assert result["load_order"] == preview["load_order"]
    assert {t["status"] for t in result["tables"]} == {"success"}, result["tables"]
    assert _count(pair[1], PARENT) == 1 and _count(pair[1], CHILD) == 2
    assert all(c["status"] in {"enabled", "unverified"} for c in result["constraints"]), result["constraints"]
    assert (tmp_path / "out" / "excel" / "volcado.xlsx").exists()


def test_append_isolates_the_duplicated_key(pair: tuple[str, str], tmp_path: Path) -> None:
    source, target = _endpoints(*pair)
    options = DumpOptions(tables=(PARENT,), truncate_target=False, on_error="isolate")

    preview = build_preview(source, target, options)
    result = run_dump(source, target, options=options, expected_structure=preview["structure_hash"],
                      outputs_dir=tmp_path / "out", work_dir=tmp_path / "work")  # fmt: skip

    table = result["tables"][0]
    if pair[1] == "oracle":
        # G32: con destino Oracle util_bbdd no aparta la PK duplicada; la tabla falla (mensaje saneado).
        assert table["status"] == "error" and "ORA-00001" in str(table["error"]), table
        assert "[SQL" not in str(table["error"])
    else:
        assert (table["status"], table["rows_rejected"]) == ("success", 1), table["error"]
        assert (tmp_path / "out" / "rejects" / "rechazos.csv").exists()
    assert _count(pair[1], PARENT) == 1


def test_duplicate_key_error_hides_the_value(pair: tuple[str, str], tmp_path: Path) -> None:
    """G34: MySQL/MariaDB y SQL Server ponen el valor de la clave en la primera línea; se enmascara."""
    if pair[1] not in {"mysql", "mariadb", "sqlserver"}:
        pytest.skip("Solo destinos que incluyen el valor de la clave en el mensaje")
    source, target = _endpoints(*pair)
    options = DumpOptions(tables=(PARENT,), truncate_target=False, on_error="raise")

    preview = build_preview(source, target, options)
    result = run_dump(source, target, options=options, expected_structure=preview["structure_hash"],
                      outputs_dir=tmp_path / "out", work_dir=tmp_path / "work")  # fmt: skip

    error = str(result["tables"][0]["error"])
    assert result["tables"][0]["status"] == "error", result["tables"]
    assert "…" in error and "'1'" not in error and "(1)" not in error, error


@pytest.mark.parametrize("engine", ["postgresql", "sqlserver", "oracle"])
def test_constraints_left_disabled_are_restored(engine: str, tmp_path: Path) -> None:
    """G31: el diario de util_bbdd (como el de un volcado cuyo proceso murió) permite reactivarlas después."""
    from util_bbdd import SyncDatabaseManager
    from util_bbdd.dump import ConstraintManager

    if not PASSWORD:
        pytest.skip("Define UTIL_BBDD_BENCH_PASSWORD para las pruebas contra los contenedores bench")
    _drop(engine)
    _execute(engine, _ddl(engine))
    journal = tmp_path / "constraints_journal.json"
    try:
        with SyncDatabaseManager(engine, _params(engine), use_pool=False) as manager:
            ConstraintManager(manager.get_sqlalchemy_engine(), SCHEMAS[engine], journal_path=journal).disable_all(
                [_ident(engine, PARENT), _ident(engine, CHILD)]
            )
        assert journal.exists()

        result = restore_constraints(Endpoint(engine, _params(engine), SCHEMAS[engine]), journal)

        assert result["pending"] is False and not journal.exists()
        assert {c["status"] for c in result["constraints"]} <= {"enabled", "unverified"}, result["constraints"]
        with pytest.raises(Exception):  # noqa: B017 (la FK vuelve a estar activa: el error depende del driver)
            _execute(engine, [f"INSERT INTO {CHILD} VALUES (99, 12345)"])
    finally:
        _drop(engine)
