"""Filtro de tablas por patrones en el plan de migración y la vista previa del volcado (util_bbdd 5.9.0, G56/G57)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from app.api.v1.schemas_dump import DumpPreviewOut
from app.api.v1.schemas_migrate import MigrationPlanOut
from app.core.errors import AppError
from app.domain.runs.errors import RunParamsError
from app.domain.runs.operations import get_operation, validate_params
from app.i18n import Msg
from app.integrations.util_bbdd import migrate
from app.integrations.util_bbdd.dump import DumpOptions, Endpoint, NoMatchingTablesError, build_preview, run_dump
from app.integrations.util_bbdd.migrate import PlannerOptions, plan_to_dict
from app.integrations.util_bbdd.table_filter import build_table_filter, filter_summary, patterns
from app.jobs.operations import dump as dump_job
from app.jobs.operations import migrate as migrate_job
from tests.unit._migration_source import oracle_int_pk_and_fk

# --- parámetros ------------------------------------------------------------------------------------------------------


def _text(exc: AppError) -> str:
    """Detalle y errores por campo en español (ADR-015: el error lleva un ``Msg``, no el texto)."""
    parts = [exc.detail.render("es")] if exc.detail else []
    parts += [e["msg"].render("es") for e in exc.extra.get("errors", []) if isinstance(e.get("msg"), Msg)]  # type: ignore[attr-defined]
    return " ".join(parts)


def test_migrate_plan_patterns_are_normalized_and_limited() -> None:
    params = validate_params(
        get_operation("migrate_plan"),
        {"source_connection": "o", "target_engine": "mariadb", "table_include": " PED* ,, PED* ", "table_exclude": ","},
    )
    assert params["table_include"] == "PED*"
    assert params["table_exclude"] is None

    with pytest.raises(RunParamsError):
        validate_params(
            get_operation("migrate_plan"),
            {"source_connection": "o", "target_engine": "mariadb", "table_exclude": "x" * 129},
        )


def test_dump_preview_takes_the_exact_list_or_the_patterns_not_both() -> None:
    base = {"source_connection": "o", "target_connection": "d"}
    operation = get_operation("dump_preview")

    assert validate_params(operation, {**base, "tables": "pedidos"})["tables"] == "pedidos"
    assert validate_params(operation, {**base, "table_include": "ped*"})["table_include"] == "ped*"
    with pytest.raises(RunParamsError) as raised:
        validate_params(operation, {**base, "tables": "pedidos", "table_exclude": "*_bak"})
    assert "no los dos" in _text(raised.value)
    with pytest.raises(RunParamsError):
        validate_params(operation, {**base, "table_include": ", ".join(f"T{i}" for i in range(101))})


def test_filter_fields_share_the_form_group() -> None:
    for name in ("migrate_plan", "dump_preview"):
        schema = get_operation(name).model.model_json_schema()["properties"]
        assert schema["table_include"]["ubw_group"] == schema["table_exclude"]["ubw_group"] == "filter"
    assert get_operation("dump_preview").model.model_json_schema()["properties"]["tables"]["ubw_group"] == "filter"


def test_table_filter_helpers() -> None:
    assert patterns(" a, ,b ") == ["a", "b"]
    assert build_table_filter(None, " , ") is None
    table_filter = build_table_filter("MVG_*, COB_*", "*_BAK")
    assert filter_summary(table_filter) == {"include": ["MVG_*", "COB_*"], "exclude": ["*_BAK"]}
    assert filter_summary(None) is None


# --- plan de migración -----------------------------------------------------------------------------------------------


def _plan(options: PlannerOptions) -> object:
    return migrate._plan("oracle", "mariadb", oracle_int_pk_and_fk(), "S", options)


def test_plan_with_filter_keeps_matching_tables_and_lists_the_frontier() -> None:
    plan = _plan(PlannerOptions(table_include="ped*"))
    data = plan_to_dict(plan, list(plan.emit_statements()))  # type: ignore[attr-defined]

    assert [t["name"].upper() for t in data["tables"]] == ["PEDIDOS"]
    assert data["filter"] == {"include": ["ped*"], "exclude": []}
    assert [name.upper() for name in data["frontier"]] == ["CLIENTES"]
    assert [w["code"] for w in data["warnings"] if w["category"] == "FOREIGN_KEY"] == ["FK_OUTSIDE_FILTER"]
    assert data["fk_mismatches"] == []  # la tabla referenciada no está en el plan: no se compara
    out = MigrationPlanOut.model_validate(json.loads(json.dumps(data)))
    assert out.filter is not None and out.filter.include == ["ped*"]


def test_plan_without_filter_has_no_filter_nor_frontier() -> None:
    plan = _plan(PlannerOptions())
    data = plan_to_dict(plan, list(plan.emit_statements()))  # type: ignore[attr-defined]

    assert data["filter"] is None
    assert data["frontier"] == []
    assert len(data["tables"]) == 2


def test_saved_plans_without_the_new_keys_still_load() -> None:
    plan = _plan(PlannerOptions())
    data = plan_to_dict(plan, list(plan.emit_statements()))  # type: ignore[attr-defined]
    del data["filter"], data["frontier"]

    out = MigrationPlanOut.model_validate(data)
    assert out.filter is None
    assert out.frontier == []


def test_filter_without_matches_is_a_form_error() -> None:
    with pytest.raises(ValueError) as caught:
        _plan(PlannerOptions(table_include="NADA_*"))

    error = migrate_job._job_error(caught.value)
    assert error.code == "invalid_params"
    assert "filtro de tablas" in error.message.render("es")


# --- vista previa y volcado ------------------------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE clientes (id INTEGER PRIMARY KEY);
CREATE TABLE pedidos (id INTEGER PRIMARY KEY, cliente_id INTEGER REFERENCES clientes(id));
CREATE TABLE lineas (id INTEGER PRIMARY KEY, pedido_id INTEGER REFERENCES pedidos(id));
CREATE TABLE pedidos_bak (id INTEGER PRIMARY KEY);
"""


def _endpoints(tmp_path: Path) -> tuple[Endpoint, Endpoint]:
    from app.integrations.util_bbdd.catalog import build_params

    endpoints = []
    for name, script in (("o.db", SCHEMA + "INSERT INTO clientes VALUES (1); INSERT INTO pedidos VALUES (1, 1);"),
                         ("d.db", SCHEMA + "INSERT INTO clientes VALUES (1);")):  # fmt: skip
        con = sqlite3.connect(tmp_path / name)
        con.executescript(script)
        con.close()
        endpoints.append(Endpoint("sqlite", build_params("sqlite", {"database": str(tmp_path / name)}), None))
    return endpoints[0], endpoints[1]


def test_preview_and_dump_with_patterns(tmp_path: Path) -> None:
    source, target = _endpoints(tmp_path)
    options = DumpOptions(table_include="PED*, lineas", table_exclude="*_bak")

    preview = build_preview(source, target, options)
    assert [t["table"] for t in preview["tables"]] == ["pedidos", "lineas"]
    assert preview["filter"] == {"include": ["PED*", "lineas"], "exclude": ["*_bak"]}
    assert preview["tables"][0]["outside_references"] == ["clientes"]
    assert DumpPreviewOut.model_validate(preview).filter is not None

    result = run_dump(
        source, target, options=options, expected_structure=preview["structure_hash"], outputs_dir=tmp_path / "out",
        work_dir=tmp_path / "work",
    )  # fmt: skip
    assert sorted(t["table"] for t in result["tables"]) == ["lineas", "pedidos"]


def test_preview_without_patterns_has_no_filter(tmp_path: Path) -> None:
    source, target = _endpoints(tmp_path)
    preview = build_preview(source, target, DumpOptions())
    assert preview["filter"] is None
    assert len(preview["tables"]) == 4


def test_preview_without_matches_is_a_form_error(tmp_path: Path) -> None:
    source, target = _endpoints(tmp_path)
    with pytest.raises(NoMatchingTablesError) as caught:
        build_preview(source, target, DumpOptions(table_include="nada_*"))

    error = dump_job._job_error(caught.value)
    assert error.code == "invalid_params"
    assert "filtro de tablas" in error.message.render("es")


def test_job_options_carry_the_patterns() -> None:
    params = get_operation("dump_preview").model.model_validate(
        {"source_connection": "o", "target_connection": "d", "table_include": "ped*"}
    )
    options = dump_job._options(params)  # type: ignore[arg-type]
    assert options.table_include == "ped*"
    assert options.tables == ()
