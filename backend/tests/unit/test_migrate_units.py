"""Fase 7: hash y JSON del plan, opciones del planner, lectura del rastro de auditoría y fallos del job."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.domain.runs.errors import RunParamsError
from app.domain.runs.operations import get_operation, validate_params
from app.integrations.util_bbdd.migrate import (
    ApplyReport,
    PlannerOptions,
    _record_failure,
    fk_mismatches,
    plan_to_dict,
    statements_hash,
)
from app.jobs.context import JobError
from app.jobs.operations.migrate import _raise_for_report


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


def test_dry_run_with_blocking_fk_fails() -> None:
    report = ApplyReport(
        mode="dry_run", statements_hash="h", statements=2, fk_blocking=True,
        fk_mismatches=[{"table": "P", "column": "C", "ref_table": "R", "ref_column": "ID"}],
    )  # fmt: skip

    with pytest.raises(JobError) as info:
        _raise_for_report(report)

    assert info.value.code == "fk_type_mismatch" and "P.C → R.ID" in info.value.message


def test_record_failure_reads_the_audit_trail(tmp_path: Path) -> None:
    audit = tmp_path / "migracion.jsonl"
    events = [
        {"kind": "statement", "status": "ok", "message": "CREATE TABLE a", "attributes": {"position": 1}},
        {"kind": "statement", "status": "ok", "message": "CREATE TABLE b", "attributes": {"position": 2}},
        {"kind": "statement", "status": "failed", "message": "CREATE TABLE c", "attributes": {"position": 3}},
        {"kind": "run", "status": "failed"},
    ]
    audit.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    report = ApplyReport(mode="apply", statements_hash="h", statements=5)

    class DriverError(Exception):
        pass

    try:
        try:
            raise DriverError("ORA-00955: name is already used\npostgresql://u:secreto@h/d [SQL: CREATE ...]")
        except DriverError as cause:
            raise RuntimeError("Sentencia 3/5 del plan falló") from cause
    except RuntimeError as exc:
        _record_failure(report, audit, exc)

    assert (report.applied, report.failed_position, report.failed_statement) == (2, 3, "CREATE TABLE c")
    assert report.error == "ORA-00955: name is already used"


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
