"""Fase 7: hash y JSON del plan, opciones del planner, plan guardado (util_bbdd 4.3.0), destino y fallos del job."""

from __future__ import annotations

import dataclasses
import json
from contextlib import nullcontext
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.domain.runs.errors import RunParamsError
from app.domain.runs.operations import get_operation, validate_params
from app.integrations.util_bbdd import migrate
from app.integrations.util_bbdd.migrate import (
    ApplyReport,
    PlanChangedError,
    PlannerOptions,
    PlanOutdatedError,
    TargetConflictError,
    apply_plan,
    create_plan,
    fk_mismatches,
    plan_to_dict,
    replan,
    restore_plan,
    statements_hash,
)
from app.jobs.context import JobError
from app.jobs.operations.migrate import _raise_for_report
from tests.unit._migration_source import fake_manager, oracle_int_pk_and_fk


def test_statements_hash_is_order_and_boundary_sensitive() -> None:
    base = statements_hash(["CREATE TABLE a (x INT)", "CREATE TABLE b (y INT)"])

    assert base == statements_hash(["CREATE TABLE a (x INT)", "CREATE TABLE b (y INT)"])
    assert base != statements_hash(["CREATE TABLE b (y INT)", "CREATE TABLE a (x INT)"])
    assert statements_hash(["ab", "c"]) != statements_hash(["a", "bc"])


def test_planner_options_drop_none_and_rename_engine() -> None:
    kwargs = PlannerOptions(charset=None, storage_engine="Aria", pg_schema="destino").kwargs()

    assert "charset" not in kwargs and "collation" not in kwargs
    assert kwargs["engine"] == "Aria" and kwargs["pg_schema"] == "destino"


def test_plan_form_options_match_the_integration() -> None:
    fields = set(get_operation("migrate_plan").model.model_fields) - {
        "source_connection",
        "source_schema",
        "target_engine",
    }

    assert fields == set(PlannerOptions.__dataclass_fields__)


@pytest.mark.parametrize(
    "bad",
    [
        {"source_connection": "o", "target_engine": "sqlite"},
        {"source_connection": "o", "target_engine": "mysql", "collation": "x y"},
        {"source_connection": "o", "target_engine": "mysql", "int_display_width": -1},
        {"source_connection": "o", "target_engine": "mysql", "word_template": "/x"},
    ],
)
def test_plan_params_rejected(bad: dict[str, object]) -> None:
    with pytest.raises(RunParamsError):
        validate_params(get_operation("migrate_plan"), bad)


@pytest.mark.parametrize(
    "bad",
    [
        {"plan_run": "nope", "target_connection": "d"},
        {"plan_run": "01JABCDEFGHJKMNPQRSTVWXYZ0", "target_connection": "d", "mode": "force"},
        {"plan_run": "01JABCDEFGHJKMNPQRSTVWXYZ0", "target_connection": "d", "dry_run_run": "x"},
    ],
)
def test_apply_params_rejected(bad: dict[str, object]) -> None:
    with pytest.raises(RunParamsError):
        validate_params(get_operation("migrate_apply"), bad)


class _Obj:
    def __init__(self, **values: Any) -> None:
        self.__dict__.update(values)


def test_plan_to_dict_serializes_tables_and_warnings() -> None:
    from util_bbdd.migrate.ir.models import MigrationWarning

    warning = MigrationWarning(table="t", column="c", category="TYPE", target_type="INT", message="m")
    column = _Obj(
        name="c", original_name="C", source_type="NUMBER(10)", target_type="INT", nullable=False, default=None,
        auto_increment=False, omit=False,
    )  # fmt: skip
    table = _Obj(
        name="t", original_name="T", comment="", primary_key=["c"], columns=[column],
        indexes=[_Obj(name="ix", columns=["c"], unique=True)], foreign_keys=[],
    )  # fmt: skip
    plan = _Obj(
        source_engine="oracle", target_engine="mariadb", source_schema="BENCH", error_count=0, warning_count=1,
        info_count=0, warnings=[warning], tables=[table], views=[], routines=[],
    )  # fmt: skip

    data = plan_to_dict(plan, ["CREATE TABLE t (c INT)"])

    json.dumps(data)  # serializable
    assert data["statements_hash"] == statements_hash(["CREATE TABLE t (c INT)"])
    assert data["tables"][0]["columns"][0]["target_type"] == "INT"
    assert data["warnings"][0]["severity"] == "WARNING" and data["warnings"][0]["proposals"] == []


def _table(name: str, columns: dict[str, str], fks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "columns": [{"name": c, "target_type": t} for c, t in columns.items()],
        "foreign_keys": fks or [],
    }


def test_fk_mismatches_ignore_int_display_width_and_catch_real_differences() -> None:
    parent = _table("CLIENTE", {"ID": "INT(11)", "CODE": "VARCHAR(10)"})
    ok = _table("PEDIDO", {"CLIENTE_ID": "int"}, [{"name": "fk1", "columns": ["CLIENTE_ID"], "ref_table": "cliente",
                                                  "ref_columns": ["id"]}])  # fmt: skip
    bad = _table(
        "LINEA",
        {"CLIENTE_ID": "DOUBLE", "CODE": "VARCHAR(20)"},
        [
            {"name": "fk2", "columns": ["CLIENTE_ID"], "ref_table": "CLIENTE", "ref_columns": ["ID"]},
            {"name": "fk3", "columns": ["CODE"], "ref_table": "CLIENTE", "ref_columns": ["CODE"]},
        ],
    )

    found = fk_mismatches([parent, ok, bad])

    assert [(m["foreign_key"], m["column_type"], m["ref_type"]) for m in found] == [
        ("fk2", "DOUBLE", "INT(11)"),
        ("fk3", "VARCHAR(20)", "VARCHAR(10)"),
    ]


@pytest.mark.parametrize("target", ["mariadb", "mysql", "sqlserver", "postgresql"])
def test_util_bbdd_gives_the_fk_the_referenced_type(target: str) -> None:
    """G28 resuelto en util_bbdd 4.3.0: Oracle ``INT`` en PK y FK ya no deja FK entre tipos distintos."""
    from util_bbdd.migrate import MigrationPlanner

    plan = MigrationPlanner(source_engine="oracle", target_engine=target).plan(oracle_int_pk_and_fk(), "S")

    data = plan_to_dict(plan, list(plan.emit_statements()))
    assert data["fk_mismatches"] == [] and data["fk_blocking"] is False and data["error_count"] == 0
    aligned = [w for w in data["warnings"] if w["code"] == "FK_TYPE_ALIGNED"]
    assert [(w["table"].upper(), str(w["column"]).upper(), w["severity"]) for w in aligned] == [
        ("PEDIDOS", "CLIENTE_ID", "INFO")
    ]


def test_dry_run_with_blocking_fk_fails() -> None:
    report = ApplyReport(
        mode="dry_run", statements_hash="h", statements=2, fk_blocking=True,
        fk_mismatches=[{"table": "P", "column": "C", "ref_table": "R", "ref_column": "ID"}],
    )  # fmt: skip

    with pytest.raises(JobError) as info:
        _raise_for_report(report)

    assert info.value.code == "fk_type_mismatch" and "P.C → R.ID" in info.value.message


def _oracle_plan(target: str = "mariadb") -> Any:
    from util_bbdd.migrate import MigrationPlanner

    return MigrationPlanner(source_engine="oracle", target_engine=target).plan(oracle_int_pk_and_fk(), "S")


def _managers(monkeypatch: pytest.MonkeyPatch, **by_engine: Any) -> None:
    """``SyncDatabaseManager(db_type, …)`` devuelve el manager falso de ese motor."""
    import util_bbdd

    monkeypatch.setattr(util_bbdd, "SyncDatabaseManager", lambda db_type, *_, **__: nullcontext(by_engine[db_type]))


def test_util_bbdd_hash_is_the_web_hash() -> None:
    """``plan.json`` de la 1.2.0 y ``migration_plan.json`` se comparan con el mismo algoritmo (G26)."""
    plan = _oracle_plan()

    assert plan.statements_sha256() == statements_hash(list(plan.emit_statements()))


def test_create_plan_saves_the_util_bbdd_plan_without_connection_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _managers(monkeypatch, oracle=oracle_int_pk_and_fk())
    params = {"host": "10.1.2.3", "user": "scott", "password": "secreto"}

    summary = create_plan(
        "oracle", params, schema="S", target_engine="mariadb", options=PlannerOptions(), outputs_dir=tmp_path
    )

    viewer = json.loads((tmp_path / "plan" / "plan.json").read_text(encoding="utf-8"))
    raw = (tmp_path / "plan" / "migration_plan.json").read_text(encoding="utf-8")
    stored = json.loads(raw)
    assert stored["format"] == "util_bbdd.migration_plan"
    assert stored["statements_sha256"] == viewer["statements_hash"] == summary["statements_hash"]
    assert not any(value in raw for value in ("10.1.2.3", "scott", "secreto"))
    assert restore_plan(stored, viewer["statements_hash"]).emit_statements() == viewer["statements"]


def test_restore_plan_rejects_another_hash_or_unreadable_data() -> None:
    stored = json.loads(json.dumps(_oracle_plan().to_dict()))

    with pytest.raises(PlanChangedError):
        restore_plan(stored, "0" * 64)
    with pytest.raises(PlanOutdatedError):
        restore_plan({**stored, "statements_sha256": "0" * 64}, stored["statements_sha256"])
    with pytest.raises(PlanOutdatedError):
        restore_plan({**stored, "format_version": 99}, stored["statements_sha256"])


def test_plans_before_1_3_0_are_planned_again(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = _oracle_plan().statements_sha256()
    _managers(monkeypatch, oracle=oracle_int_pk_and_fk())

    plan = replan(("oracle", {}), "mariadb", schema="S", options=PlannerOptions(), expected_hash=expected)

    assert plan.statements_sha256() == expected
    with pytest.raises(PlanChangedError):
        replan(("oracle", {}), "mariadb", schema="S", options=PlannerOptions(), expected_hash="0" * 64)


def test_dry_run_reports_existing_tables_and_views_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from util_bbdd.metadata.model import TableMeta, ViewMeta

    target = fake_manager("mariadb", TableMeta("clientes", None), ViewMeta("PEDIDOS", "SELECT 1", None, False))
    _managers(monkeypatch, mariadb=target)
    plan = _oracle_plan()

    report = apply_plan(plan, ("mariadb", {}), mode="dry_run", outputs_dir=tmp_path)

    assert [name.lower() for name in report.conflicts] == ["clientes", "pedidos"]
    assert report.statements == len(plan.emit_statements()) and report.applied == 0
    target.get_sqlalchemy_engine.assert_not_called()
    with pytest.raises(TargetConflictError):
        apply_plan(plan, ("mariadb", {}), mode="apply", outputs_dir=tmp_path)


def _target_cursor(target: MagicMock) -> MagicMock:
    cursor: MagicMock = target.get_sqlalchemy_engine.return_value.raw_connection.return_value.cursor.return_value
    return cursor


def test_apply_runs_the_restored_plan_and_counts_the_statements(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = fake_manager("mariadb")
    _managers(monkeypatch, mariadb=target)
    plan = restore_plan(_oracle_plan().to_dict(), _oracle_plan().statements_sha256())

    report = apply_plan(plan, ("mariadb", {}), mode="apply", outputs_dir=tmp_path)

    assert report.error is None and report.applied == report.statements == _target_cursor(target).execute.call_count
    assert (tmp_path / "audit" / "migracion.jsonl").exists()


def test_partial_apply_takes_the_failed_statement_from_util_bbdd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class DriverError(Exception):
        pass

    target = fake_manager("mariadb")
    _target_cursor(target).execute.side_effect = [
        None,
        DriverError("(1050) Table already exists\nmysql://u:secreto@h/d [SQL: CREATE ...]"),
    ]
    _managers(monkeypatch, mariadb=target)
    plan = _oracle_plan()

    report = apply_plan(plan, ("mariadb", {}), mode="apply", outputs_dir=tmp_path)

    assert (report.applied, report.failed_position) == (1, 2)
    assert report.failed_statement == plan.emit_statements()[1].strip().splitlines()[0]
    assert report.error == "(1050) Table already exists"


def test_apply_reports_each_statement_and_stops_between_statements_when_cancelled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G1 (util_bbdd 4.3.0): un evento por sentencia; cancelar para antes de la siguiente y las aplicadas quedan."""
    from app.integrations.util_bbdd.progress import RunProgress

    target = fake_manager("mariadb")
    _managers(monkeypatch, mariadb=target)
    plan = _oracle_plan()
    reported: list[tuple[str, int | None]] = []
    polls = iter([False, True])  # se pide cancelar después de la primera sentencia
    progress = RunProgress(
        lambda message, pct: reported.append((message, pct)),
        lambda: next(polls, True),
        ["statements"],
        {"statements": "Sentencias"},
        poll_seconds=0,
    )

    report = apply_plan(plan, ("mariadb", {}), mode="apply", outputs_dir=tmp_path, progress=progress)

    assert report.cancelled and report.error is None
    assert report.applied == _target_cursor(target).execute.call_count == 1 < report.statements
    assert reported[0] == (f"Sentencias: 0 de {report.statements}", 0)
    assert reported[1][0].startswith(f"Sentencias: 1 de {report.statements} (CREATE TABLE")
    with pytest.raises(JobError) as info:
        _raise_for_report(report)
    assert info.value.code == "cancelled" and f"aplicadas 1 de {report.statements}" in info.value.message


def test_blocked_or_fk_blocking_plans_never_reach_the_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = fake_manager("mariadb")
    _managers(monkeypatch, mariadb=target)
    plan = _oracle_plan()
    monkeypatch.setattr(migrate, "plan_to_dict", lambda *_: {"statements_hash": "h", "fk_mismatches": [{}],
                                                             "fk_blocking": True})  # fmt: skip

    with pytest.raises(migrate.FkTypeMismatchError):
        apply_plan(plan, ("mariadb", {}), mode="apply", outputs_dir=tmp_path)
    plan.warnings[0] = dataclasses.replace(plan.warnings[0], severity="ERROR")
    with pytest.raises(migrate.PlanBlockedError):
        apply_plan(plan, ("mariadb", {}), mode="apply", outputs_dir=tmp_path)
    target.get_sqlalchemy_engine.assert_not_called()


def test_dry_run_with_conflicts_or_invalid_views_fails() -> None:
    conflict = ApplyReport(mode="dry_run", statements_hash="h", statements=2, conflicts=["clientes"])
    invalid = ApplyReport(mode="dry_run", statements_hash="h", statements=2, views=[{"view": "v", "valid": False}])
    skipped = ApplyReport(mode="dry_run", statements_hash="h", statements=2, views=[{"view": "v", "valid": None}])

    with pytest.raises(JobError) as first:
        _raise_for_report(conflict)
    with pytest.raises(JobError) as second:
        _raise_for_report(invalid)
    _raise_for_report(skipped)

    assert first.value.code == "target_conflict" and "clientes" in first.value.message
    assert second.value.code == "view_invalid"


def test_partial_apply_reports_position_and_applied() -> None:
    report = ApplyReport(
        mode="apply", statements_hash="h", statements=5, applied=2, failed_position=3, error="ORA-00955"
    )

    with pytest.raises(JobError) as info:
        _raise_for_report(report)

    assert info.value.code == "apply_partial"
    assert "3/5" in info.value.message and "aplicadas 2" in info.value.message
