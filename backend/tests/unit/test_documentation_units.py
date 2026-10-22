"""Fase 5: parámetros de documentación y grafos, ``imprimir`` de util_bbdd, schema por motor y token del sitio."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.security import site_token, verify_site_token
from app.domain.runs.errors import RunParamsError
from app.domain.runs.operations import get_operation, validate_params
from app.integrations.util_bbdd import documentation
from app.integrations.util_bbdd.documentation import (
    DocumentationOptions,
    GraphvizMissingError,
    SchemaNotSupportedError,
    build_imprimir,
    with_schema,
)
from app.jobs.context import JobError
from app.jobs.operations.documentation import _job_error

# --- parámetros --------------------------------------------------------------------------------------------------


def _validate(operation: str, params: dict[str, object]) -> dict[str, object]:
    return validate_params(get_operation(operation), params)


def test_documentation_defaults_and_alias() -> None:
    params = _validate("documentation", {"connection": "origen", "schema": "ventas"})

    assert params["schema"] == "ventas" and "schema_name" not in params
    assert (params["word"], params["excel"], params["html"], params["graphs"]) == (True, True, True, True)
    assert params["routines"] is False


@pytest.mark.parametrize(
    "bad",
    [
        {"connection": "origen", "word": False, "excel": False, "html": False},
        {"connection": "origen", "graph_depth": 4},
        {"connection": "origen", "graph_direction": "sideways"},
        {"connection": "origen", "plantilla_word": "/etc/passwd"},
        {"connection": "origen", "schema": "public'; DROP TABLE x; --"},
        {"connection": "origen", "schema": 'a"b'},
        {"connection": "../x"},
        {},
    ],
)
def test_documentation_rejects(bad: dict[str, object]) -> None:
    with pytest.raises(RunParamsError):
        _validate("documentation", bad)


@pytest.mark.parametrize(
    "bad",
    [
        {"connection": "origen", "format": "pdf"},
        {"connection": "origen", "max_subnodes": 1},
        {"connection": "origen", "column_mode": "nada"},
        {"connection": "origen", "output_dir": "salida"},
        {"connection": "origen", "table": "pedidos where 1=1;"},
        {"connection": "origen", "table": "x" * 200},
    ],
)
def test_graph_rejects(bad: dict[str, object]) -> None:
    with pytest.raises(RunParamsError):
        _validate("relationship_graph", bad)


@pytest.mark.parametrize("name", ["public", "dbo", "BENCH", "mi_schema$1", "Ventas 2026", "sch.ema", "año-1"])
def test_object_names_accepted(name: str) -> None:
    assert _validate("relationship_graph", {"connection": "o", "schema": name, "table": name})["table"] == name


def test_params_carry_groups_and_options() -> None:
    params = {p.name: p for p in get_operation("relationship_graph").params}

    assert params["direction"].options == ["both", "outgoing", "incoming"]
    assert params["direction"].group == "graph"
    assert params["schema"].type == "string" and params["schema"].required is False
    assert params["connection"].type == "connection" and params["connection"].group is None


# --- capa de integración -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("db_type", "key"),
    [
        ("postgresql", "schema"),
        ("sqlserver", "schema"),
        ("hsqldb", "schema"),
        ("mysql", "database"),
        ("mariadb", "database"),
    ],
)
def test_with_schema_sets_engine_key(db_type: str, key: str) -> None:
    base = {"host": "h", "user": "u"}

    assert with_schema(db_type, base, "ventas") == {**base, key: "ventas"}
    assert with_schema(db_type, base, None) is base
    assert "schema" not in base and "database" not in base


def test_with_schema_sqlite_ignores_it() -> None:
    assert with_schema("sqlite", {"database": "x.db"}, "main") == {"database": "x.db"}


def test_with_schema_oracle_only_user_schema() -> None:
    params = {"user": "ventas", "service_name": "FREEPDB1"}

    assert with_schema("oracle", params, "VENTAS") is params
    assert with_schema("oracle", params, '"ventas"') is params
    with pytest.raises(SchemaNotSupportedError, match="VENTAS"):
        with_schema("oracle", params, "HR")


def test_build_imprimir_maps_options() -> None:
    imprimir = build_imprimir(
        DocumentationOptions(formats=("html",), tables=False, table_ddl=True, routines=True, graph_depth=2)
    )

    assert imprimir["tablas"]["imprimir_tablas"] is False
    assert imprimir["tablas"]["ddl"] is False  # sin tablas, nada de sus secciones
    assert imprimir["rutinas"] == {"imprimir_procedures": True, "imprimir_function": True}
    assert imprimir["grafo"] == {"enabled": True, "max_depth": 2, "direction": "both", "workers": 2}
    assert "plantilla_word" not in imprimir


def test_options_fields_match_params() -> None:
    """Cada opción de la capa de integración tiene su campo en el formulario (y viceversa salvo formatos)."""
    params = set(get_operation("documentation").model.model_fields) - {"connection", "schema_name"}
    options = set(DocumentationOptions.__dataclass_fields__) - {"formats"}

    assert params - {"word", "excel", "html"} == options


def test_graphviz_missing_is_detected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(documentation.shutil, "which", lambda _: None)

    with pytest.raises(GraphvizMissingError):
        documentation.generate_documentation(
            "sqlite",
            {"database": str(tmp_path / "x.db")},
            schema=None,
            options=DocumentationOptions(formats=("html",)),
            outputs_dir=tmp_path,
            work_dir=tmp_path / "work",
            name="doc",
        )


def test_job_errors_never_echo_driver_text() -> None:
    class DriverError(Exception):
        pass

    error = _job_error(DriverError("password=secreto host=10.0.0.1"))

    assert isinstance(error, JobError)
    assert "secreto" not in error.message and "10.0.0.1" not in error.message
    assert _job_error(SchemaNotSupportedError("x")).code == "invalid_params"
    assert _job_error(GraphvizMissingError("x")).code == "graphviz_missing"


# --- token del sitio ---------------------------------------------------------------------------------------------


def test_site_token_roundtrip_and_tampering(settings: Settings) -> None:
    token = site_token(settings, run_id="R1", user_id=7, expires=2_000)

    assert verify_site_token(settings, token, run_id="R1", now=1_000) == 7
    assert verify_site_token(settings, token, run_id="R2", now=1_000) is None
    assert verify_site_token(settings, token, run_id="R1", now=2_001) is None
    assert verify_site_token(settings, token.replace("7.", "8.", 1), run_id="R1", now=1_000) is None
    assert verify_site_token(settings, "7.2000", run_id="R1", now=1_000) is None
