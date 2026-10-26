"""Migración DDL (Fase 7) contra los contenedores bench, **escribiendo** en el destino (fuera del CI).

Crea ``ubw_it_cliente``/``ubw_it_pedido`` en el origen, planifica, valida en modo seco, aplica y limpia el destino.
Comprueba el hash ante cambios del origen, los conflictos (tablas y vistas) y un fallo a medias real con su rastro.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from app.integrations.util_bbdd import migrate
from app.integrations.util_bbdd.migrate import (
    PlanChangedError,
    PlannerOptions,
    TargetConflictError,
    apply_plan,
    create_plan,
)
from tests.integration.test_bench_engines import PASSWORD
from tests.integration.test_bench_explorer import CHILD, PARENT, SCHEMAS, _ddl, _execute, _params

pytestmark = pytest.mark.integration

#: Combinaciones que se aplican de verdad. Oracle → MariaDB: con util_bbdd 4.3.0 su FK ya tiene el tipo de la PK (G28).
PAIRS = [
    ("postgresql", "mysql"), ("mysql", "postgresql"), ("sqlserver", "postgresql"), ("mariadb", "oracle"),
    ("oracle", "mariadb"),
]  # fmt: skip
ENGINES = ("oracle", "mariadb", "mysql", "sqlserver", "postgresql")


#: Nombres posibles de las tablas de prueba en cualquier motor (Oracle → MariaDB las crea en mayúsculas, y MariaDB
#: distingue mayúsculas en Linux). Hijo antes que padre por la FK.
ALL_NAMES = [CHILD, CHILD.upper(), PARENT, PARENT.upper()]


def _drop(engine: str, names: list[str] = ALL_NAMES) -> None:
    """Una sentencia por transacción: en PostgreSQL y SQL Server un DROP fallido aborta la transacción entera."""
    for name in names:
        for statement in (f"DROP VIEW {name}", f"DROP TABLE {name}"):
            try:
                _execute(engine, [statement], ignore_errors=True)
            except Exception:  # noqa: S110 (SQL Server falla también en el COMMIT de una transacción abortada)
                pass


@pytest.fixture
def source_tables() -> Iterator[None]:
    if not PASSWORD:
        pytest.skip("Define UTIL_BBDD_BENCH_PASSWORD para las pruebas contra los contenedores bench")
    yield


def _prepare(source: str, target: str) -> None:
    _drop(source)
    _drop(target)
    _execute(source, _ddl(source))


def _plan(source: str, target: str, out: Path) -> dict[str, Any]:
    create_plan(
        source, _params(source), schema=SCHEMAS[source], target_engine=target, options=PlannerOptions(),
        outputs_dir=out,
    )  # fmt: skip
    data: dict[str, Any] = json.loads((out / "plan" / "plan.json").read_text(encoding="utf-8"))
    return data


def _apply(source: str, target: str, plan: dict[str, Any], mode: Any, out: Path) -> migrate.ApplyReport:
    return apply_plan(
        (source, _params(source)), (target, _params(target)), schema=plan["source_schema"],
        options=PlannerOptions(), expected_hash=plan["statements_hash"], mode=mode, outputs_dir=out,
    )  # fmt: skip


@pytest.mark.parametrize(("source", "target"), PAIRS)
def test_plan_dry_run_apply_and_conflicts(source: str, target: str, source_tables: None, tmp_path: Path) -> None:
    _prepare(source, target)
    try:
        plan = _plan(source, target, tmp_path / "plan")
        assert plan["error_count"] == 0, plan["warnings"]
        assert {t["name"].lower() for t in plan["tables"]} == {PARENT, CHILD}

        dry = _apply(source, target, plan, "dry_run", tmp_path / "dry")
        assert dry.conflicts == [] and dry.applied == 0

        done = _apply(source, target, plan, "apply", tmp_path / "apply")
        assert done.error is None and done.applied == done.statements == len(plan["statements"])
        audit = (tmp_path / "apply" / "audit" / "migracion.jsonl").read_text(encoding="utf-8")
        assert sum(1 for line in audit.splitlines() if json.loads(line)["kind"] == "statement") == done.statements

        again = _apply(source, target, plan, "dry_run", tmp_path / "again")
        assert {c.lower() for c in again.conflicts} == {PARENT, CHILD}
        with pytest.raises(TargetConflictError):
            _apply(source, target, plan, "apply", tmp_path / "blocked")
    finally:
        _drop(target)
        _drop(source)


def test_oracle_int_foreign_key_gets_the_primary_key_type(source_tables: None, tmp_path: Path) -> None:
    """G28 (util_bbdd 4.3.0): Oracle ``INT`` es ``NUMBER`` sin precisión; la FK recibe el tipo de la PK."""
    source, target = "oracle", "mariadb"
    _prepare(source, target)
    try:
        plan = _plan(source, target, tmp_path / "plan")
        assert plan["fk_mismatches"] == [] and plan["fk_blocking"] is False
        assert any(w["code"] == "FK_TYPE_ALIGNED" for w in plan["warnings"])

        dry = _apply(source, target, plan, "dry_run", tmp_path / "dry")
        assert dry.fk_mismatches == [] and dry.fk_blocking is False
    finally:
        _drop(target)
        _drop(source)


def test_changed_source_invalidates_the_plan(source_tables: None, tmp_path: Path) -> None:
    source, target = "postgresql", "mysql"
    _prepare(source, target)
    try:
        plan = _plan(source, target, tmp_path / "plan")
        _execute(source, [f"ALTER TABLE {PARENT} ADD COLUMN email VARCHAR(50)"])

        with pytest.raises(PlanChangedError):
            _apply(source, target, plan, "dry_run", tmp_path / "dry")
    finally:
        _drop(target)
        _drop(source)


def test_view_with_a_table_name_is_a_conflict_and_a_real_partial_failure(
    source_tables: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target = "postgresql", "mysql"
    _prepare(source, target)
    try:
        plan = _plan(source, target, tmp_path / "plan")
        order = [t["name"] for t in plan["tables"]]
        _execute(target, [f"CREATE VIEW {order[-1]} AS SELECT 1 AS x"])

        dry = _apply(source, target, plan, "dry_run", tmp_path / "dry")
        assert dry.conflicts == [order[-1]]

        # Sin la comprobación de conflictos, la última sentencia falla y las anteriores quedan aplicadas (G27).
        monkeypatch.setattr(migrate, "_target_tables", lambda *_: [])
        report = _apply(source, target, plan, "apply", tmp_path / "apply")
        assert report.error is not None and "secreto" not in report.error
        assert report.failed_position == len(plan["statements"])
        assert report.applied == len(plan["statements"]) - 1
    finally:
        _drop(target)
        _drop(source)


@pytest.mark.parametrize("source", ENGINES)
def test_every_supported_combination_plans(source: str, source_tables: None, tmp_path: Path) -> None:
    _drop(source)
    _execute(source, _ddl(source))
    try:
        for target in ENGINES:
            if target == source:
                continue
            plan = _plan(source, target, tmp_path / target)
            assert len(plan["tables"]) == 2, (source, target)
            assert plan["statements"], (source, target)
    finally:
        _drop(source)


def test_conflicts_are_checked_in_pg_schema(source_tables: None, tmp_path: Path) -> None:
    """Con ``pg_schema`` el script crea las tablas en ese schema (``SET search_path``): ahí se buscan los conflictos."""
    source, target, pg_schema = "mysql", "postgresql", "ubw_it_destino"
    _prepare(source, target)
    _execute(target, [f"DROP SCHEMA IF EXISTS {pg_schema} CASCADE"])
    try:
        _execute(target, [f"CREATE SCHEMA {pg_schema}", f"CREATE TABLE {pg_schema}.{PARENT} (id INT)"])
        options = PlannerOptions(pg_schema=pg_schema)
        out = tmp_path / "plan"
        create_plan(source, _params(source), schema=SCHEMAS[source], target_engine=target, options=options,
                    outputs_dir=out)  # fmt: skip
        plan = json.loads((out / "plan" / "plan.json").read_text(encoding="utf-8"))

        def run(mode: Any, folder: str) -> migrate.ApplyReport:
            return apply_plan(
                (source, _params(source)), (target, _params(target)), schema=plan["source_schema"], options=options,
                expected_hash=plan["statements_hash"], mode=mode, outputs_dir=tmp_path / folder,
            )  # fmt: skip

        assert [c.lower() for c in run("dry_run", "dry").conflicts] == [PARENT]
        with pytest.raises(TargetConflictError):
            run("apply", "apply")
    finally:
        _execute(target, [f"DROP SCHEMA IF EXISTS {pg_schema} CASCADE"])
        _drop(source)
