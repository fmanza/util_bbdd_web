"""Documentación y grafos (Fase 5) contra los contenedores bench (fuera del CI; ver ``test_bench_engines.py``).

Comprueba, por motor, que el schema llega a util_bbdd como argumento (``schema=``, GAPS G22) y que en Oracle se puede
leer otro owner que el usuario de la conexión (G21; util_bbdd 4.1.0).
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

import pytest

from app.integrations.util_bbdd.documentation import (
    DocumentationOptions,
    GraphOptions,
    generate_documentation,
    generate_graphs,
)
from tests.integration.test_bench_explorer import CHILD, PARENT, SCHEMAS, _ident, _params, db_type  # noqa: F401

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz (dot) no está instalado"),
]


def test_documentation_of_the_bench_schema(db_type: str, tmp_path: Path) -> None:  # noqa: F811
    outputs = tmp_path / "outputs"

    summary = generate_documentation(
        db_type,
        _params(db_type),
        schema=SCHEMAS[db_type],
        options=DocumentationOptions(formats=("excel", "html"), graphs=False, views=False),
        outputs_dir=outputs,
        work_dir=tmp_path / "work",
        name="documentacion",
    )

    assert summary["tables"] >= 2
    assert set(summary["formats"]) == {"excel", "html"}
    with zipfile.ZipFile(outputs / summary["formats"]["excel"]) as xlsx:
        strings = "".join(xlsx.read(name).decode("utf-8") for name in xlsx.namelist() if name.endswith(".xml")).lower()
    assert PARENT in strings and CHILD in strings
    site = "".join(p.read_text(encoding="utf-8", errors="replace") for p in (outputs / "html").rglob("*.html"))
    assert PARENT in site.lower()


def test_graph_of_the_parent_table(db_type: str, tmp_path: Path) -> None:  # noqa: F811
    summary = generate_graphs(
        db_type,
        _params(db_type),
        schema=SCHEMAS[db_type],
        options=GraphOptions(table=_ident(db_type, PARENT)),
        output_dir=tmp_path,
    )

    assert summary["files"]
    svg = (tmp_path / summary["files"][0]).read_text(encoding="utf-8").lower()
    assert CHILD in svg


def test_oracle_other_owner_is_read(db_type: str, tmp_path: Path) -> None:  # noqa: F811
    """G21 (util_bbdd 4.1.0): ``SYS.DUAL`` se dibuja con la conexión del usuario del bench."""
    if db_type != "oracle":
        pytest.skip("Solo Oracle (GAPS G21)")
    summary = generate_graphs(
        db_type, _params(db_type), schema="SYS", options=GraphOptions(table="DUAL"), output_dir=tmp_path
    )

    assert summary["files"]
