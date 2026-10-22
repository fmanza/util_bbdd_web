"""Fase 6: parámetros de ``compare``, schema por lado, etiquetas sin infraestructura, JSON del diff y evolución."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.domain.runs.diff import evolution, leaf_items
from app.domain.runs.errors import RunParamsError
from app.domain.runs.operations import get_operation, validate_params
from app.integrations.util_bbdd.compare import (
    MERMAID_STUB_PATH,
    SchemaNotFoundError,
    Side,
    SideError,
    diff_to_dict,
    localize_mermaid,
    relabel,
    resolve_schema,
    sql_dialect_for,
)
from app.jobs.operations.compare import _job_error

# --- parámetros --------------------------------------------------------------------------------------------------


def _validate(params: dict[str, object]) -> dict[str, object]:
    return validate_params(get_operation("compare"), params)


def test_compare_defaults() -> None:
    params = _validate({"source_connection": "a", "target_connection": "b"})

    assert (params["tables"], params["views"], params["routines"]) == (True, True, False)
    assert (params["html"], params["word"], params["sql"], params["sql_dialect"]) == (True, False, True, "auto")


@pytest.mark.parametrize(
    "bad",
    [
        {"source_connection": "a"},
        {"source_connection": "a", "target_connection": "b", "tables": False, "views": False},
        {"source_connection": "a", "target_connection": "b", "target_schema": "x;y"},
        {"source_connection": "a", "target_connection": "b", "sql_dialect": "db2"},
        {"source_connection": "a", "target_connection": "b", "word_template_path": "/tmp/x.docx"},  # noqa: S108
    ],
)
def test_compare_rejects(bad: dict[str, object]) -> None:
    with pytest.raises(RunParamsError):
        _validate(bad)


def test_compare_form_has_two_connections_and_groups() -> None:
    params = {p.name: p for p in get_operation("compare").params}

    assert params["source_connection"].type == params["target_connection"].type == "connection"
    assert params["indexes"].group == "scope" and params["sql"].group == "reports"
    assert params["sql_dialect"].options is not None and "auto" in params["sql_dialect"].options


# --- capa de integración -----------------------------------------------------------------------------------------


class _Dialect:
    def __init__(self, normalize: bool) -> None:
        self.requires_name_normalize = normalize

    def denormalize_name(self, name: str) -> str:
        return name.upper() if name.islower() else name


def test_resolve_schema_exact_and_case_insensitive() -> None:
    plain = _Dialect(normalize=False)

    assert resolve_schema("source", None, ["dbo"], plain) is None
    assert resolve_schema("source", "dbo", ["dbo", "sales"], plain) == "dbo"
    assert resolve_schema("source", "DBO", ["dbo", "sales"], plain) == "dbo"


def test_resolve_schema_oracle_uses_the_normalized_name() -> None:
    oracle = _Dialect(normalize=True)

    # SQLAlchemy entrega ``bench`` para el schema real ``BENCH``; el Inspector espera ``bench``.
    assert resolve_schema("target", "BENCH", ["bench", "system"], oracle) == "bench"
    assert resolve_schema("target", "bench", ["bench", "system"], oracle) == "bench"


def test_resolve_schema_missing_or_ambiguous() -> None:
    with pytest.raises(SchemaNotFoundError, match="destino"):
        resolve_schema("target", "nope", ["dbo"], _Dialect(normalize=False))
    with pytest.raises(SchemaNotFoundError, match="origen"):
        resolve_schema("source", "ab", ["Ab", "aB"], _Dialect(normalize=False))


@pytest.mark.parametrize(
    ("option", "target", "expected"),
    [("auto", "postgresql", "postgresql"), ("auto", "hsqldb", "generic"), ("mysql", "oracle", "mysql")],
)
def test_sql_dialect(option: str, target: str, expected: str) -> None:
    assert sql_dialect_for(option, target) == expected


def _diff() -> Any:
    from util_bbdd.comparar import ColumnDiff, SchemaDiff, TableDiff

    return SchemaDiff(
        source_label="postgresql://ana@10.0.0.7:5432/ventas [public]",
        target_label="sqlite:////srv/ubw/files/destino.db",
        table_diffs=(
            TableDiff("clientes", "modified", column_diffs=(ColumnDiff("nombre", "nullable", "False", "True"),)),
        ),
        summary="Tablas: 0 añadidas, 0 eliminadas, 1 modificadas",
        source_short_label="pg_7_ventas",
        target_short_label="destino",
    )


def test_relabel_and_json_have_no_infrastructure() -> None:
    source = Side("postgresql", {"password": "x"}, "public", "origen")
    target = Side("sqlite", {}, None, "destino")

    data = diff_to_dict(relabel(_diff(), source, target))

    text = repr(data)
    assert data["source_label"] == "origen (postgresql) [public]" and data["target_label"] == "destino (sqlite)"
    assert "10.0.0.7" not in text and "/srv/ubw" not in text and "ana@" not in text
    assert (data["format"], data["has_differences"], data["total_leaf_differences"]) == (1, True, 1)


def test_job_errors_name_the_side_without_driver_text() -> None:
    class DriverError(Exception):
        pass

    error = _job_error(SideError("target", DriverError("host=10.0.0.7 password=secreto")))

    assert error.message.startswith("Destino:")
    assert "secreto" not in error.message and "10.0.0.7" not in error.message
    assert _job_error(SchemaNotFoundError("source", "x")).code == "invalid_params"


# --- evolución ---------------------------------------------------------------------------------------------------

BASELINE: dict[str, Any] = {
    "source_label": "a (sqlite)",
    "target_label": "b (sqlite)",
    "table_diffs": [
        {"table_name": "facturas", "status": "added"},
        {
            "table_name": "Clientes",
            "status": "modified",
            "column_diffs": [
                {"column_name": "nombre", "attribute": "type", "source_value": "VARCHAR(80)", "target_value": "TEXT"}
            ],
            "index_diffs": [],
            "fk_diffs": [],
            "comment_diffs": [
                {"object_name": "Clientes", "column_name": None, "source_comment": "x", "target_comment": ""}
            ],
        },
    ],
    "view_diffs": [{"view_name": "v", "status": "modified"}],
    "routine_diffs": [],
}


def test_leaf_items_cover_every_kind() -> None:
    kinds = {(i.kind, i.name, i.attribute) for i in leaf_items(BASELINE)}

    assert kinds == {
        ("table", "facturas", None),
        ("column", "nombre", "type"),
        ("comment", "Clientes", "table"),
        ("view", "v", None),
    }


def test_evolution_new_resolved_persisting_and_case() -> None:
    current: dict[str, Any] = {
        **BASELINE,
        "table_diffs": [
            {
                "table_name": "clientes",  # mismo objeto aunque cambie la caja
                "status": "modified",
                "column_diffs": [
                    {"column_name": "nombre", "attribute": "type", "source_value": "VARCHAR(80)", "target_value": "X"},
                    {"column_name": "email", "attribute": "existence", "source_value": "1", "target_value": "0"},
                ],
            }
        ],
        "view_diffs": [],
    }

    result = evolution(current, BASELINE)

    assert {(i.kind, i.name) for i in result.new} == {("column", "email")}
    assert {(i.kind, i.name) for i in result.resolved} == {
        ("table", "facturas"),
        ("comment", "Clientes"),
        ("view", "v"),
    }
    assert [(i.name, i.target) for i in result.persisting] == [("nombre", "X")]
    assert result.labels_match is True
    assert evolution({**current, "target_label": "c (sqlite)"}, BASELINE).labels_match is False


# --- Mermaid (G25) -----------------------------------------------------------------------------------------------


def test_localize_mermaid_replaces_the_cdn_script(tmp_path: Path) -> None:
    html = tmp_path / "index.html"
    html.write_text(
        '<main></main>\n<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>\n'
        "<script>mermaid.initialize({});</script>",
        encoding="utf-8",
    )

    assert localize_mermaid(html) is True

    content = html.read_text(encoding="utf-8")
    assert "https://" not in content
    assert f'<script src="{MERMAID_STUB_PATH}"></script>' in content
    assert "window.mermaid" in (tmp_path / MERMAID_STUB_PATH).read_text(encoding="utf-8")


def test_localize_mermaid_leaves_other_reports_alone(tmp_path: Path) -> None:
    html = tmp_path / "index.html"
    html.write_text("<script>var x = 1;</script>", encoding="utf-8")

    assert localize_mermaid(html) is False
    assert html.read_text(encoding="utf-8") == "<script>var x = 1;</script>"
    assert not (tmp_path / MERMAID_STUB_PATH).exists()
