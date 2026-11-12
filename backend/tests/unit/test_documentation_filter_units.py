"""Filtro de tablas y vistas de la documentación (util_bbdd 5.5.0): parámetros, ``imprimir["filtro"]``, frontera y
``README.md`` del Markdown."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.domain.runs.errors import RunParamsError
from app.domain.runs.operations import get_operation, split_patterns, validate_params
from app.integrations.util_bbdd.documentation import DocumentationOptions, build_imprimir, generate_documentation
from app.jobs.operations.documentation import _frontier_text


def _validate(params: dict[str, object]) -> dict[str, object]:
    return validate_params(get_operation("documentation"), {"connection": "origen", **params})


def test_patterns_are_normalized() -> None:
    params = _validate({"table_include": " MVG_* ,, COB_*, MVG_* ", "table_exclude": " , "})

    assert params["table_include"] == "MVG_*, COB_*"
    assert params["table_exclude"] is None
    assert params["table_frontier"] is True
    assert split_patterns("a, b,,a") == ("a", "b")
    assert split_patterns(None) == ()


@pytest.mark.parametrize(
    "params",
    [
        {"table_include": ", ".join(f"T{i}" for i in range(101))},
        {"table_exclude": "x" * 129},
        {"table_include": "MVG_*\n"},
    ],
)
def test_invalid_patterns_are_rejected(params: dict[str, object]) -> None:
    with pytest.raises(RunParamsError):
        _validate(params)


def test_imprimir_has_filter_only_with_patterns() -> None:
    assert "filtro" not in build_imprimir(DocumentationOptions(formats=("word",)))
    options = DocumentationOptions(
        formats=("markdown",), table_include="MVG_*, COB_*", table_exclude=None, table_frontier=False
    )
    assert build_imprimir(options)["filtro"] == {"incluir": ["MVG_*", "COB_*"], "excluir": [], "frontera": False}


def test_frontier_text() -> None:
    assert _frontier_text([]) == ""
    assert _frontier_text(["A"]) == "; frontera del filtro: 1 tabla (A)"
    names = [f"T{i}" for i in range(7)]
    assert _frontier_text(names) == "; frontera del filtro: 7 tablas (T0, T1, T2, T3, T4…)"


def test_generate_with_filter_returns_frontier_and_readme(tmp_path: Path) -> None:
    database = tmp_path / "bd.db"
    con = sqlite3.connect(database)
    con.executescript(
        "CREATE TABLE AUX_PAIS (id INTEGER PRIMARY KEY);"
        "CREATE TABLE MVG_CLIENTE (id INTEGER PRIMARY KEY, pais_id INTEGER REFERENCES AUX_PAIS(id));"
        "CREATE TABLE MVG_CLIENTE_BAK (id INTEGER PRIMARY KEY);"
        "CREATE TABLE OTRA (id INTEGER PRIMARY KEY);"
    )
    con.close()
    outputs = tmp_path / "outputs"

    summary = generate_documentation(
        "sqlite",
        {"database": str(database)},
        schema=None,
        options=DocumentationOptions(formats=("markdown",), graphs=False, table_include="mvg_*", table_exclude="*_BAK"),
        outputs_dir=outputs,
        work_dir=tmp_path / "work",
        name="documentacion",
    )

    assert summary["tables"] == 1
    assert summary["frontier"] == ["AUX_PAIS"]
    root = outputs / "markdown" / "documentacion"
    assert (root / "README.md").is_file()
    assert "## Alcance" in (root / "docs" / "index.md").read_text(encoding="utf-8")
