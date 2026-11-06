"""Documentación Markdown (util_bbdd 5.3.0): bloque ``imprimir["markdown"]``, condición de Graphviz, mensajes sin rutas
del servidor y comprobación de los mapas de trazabilidad al subirlos."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.domain.templates.errors import TemplateContentError
from app.domain.templates.files import base_template, check_template, kind_for, stored_suffix
from app.integrations.util_bbdd import documentation as doc
from app.integrations.util_bbdd.documentation import (
    DocumentationOptions,
    MarkdownInputError,
    MarkdownInputs,
    build_imprimir,
    generate_documentation,
    markdown_input_error,
    public_message,
)


def test_imprimir_has_no_markdown_block_without_markdown() -> None:
    imprimir = build_imprimir(DocumentationOptions(formats=("word", "html")), markdown=MarkdownInputs())

    assert "markdown" not in imprimir


def test_imprimir_markdown_block(tmp_path: Path) -> None:
    inputs = MarkdownInputs(
        mermaid_js=tmp_path / "mermaid.min.js", trace_map=tmp_path / "t.toml", previous=tmp_path / "catalog.json"
    )
    options = DocumentationOptions(formats=("markdown",), markdown_site_name="BD", markdown_diagram_depth=3)

    block = build_imprimir(options, markdown=inputs)["markdown"]

    assert block == {
        "max_diagram_depth": 3,
        "site_name": "BD",
        "mermaid_js": str(tmp_path / "mermaid.min.js"),
        "trace_map": str(tmp_path / "t.toml"),
        "previous": str(tmp_path / "catalog.json"),
    }
    assert build_imprimir(DocumentationOptions(formats=("markdown",)))["markdown"] == {"max_diagram_depth": 2}


def test_public_message_hides_server_paths(tmp_path: Path) -> None:
    trace = tmp_path / "run" / "inputs" / "plantilla_trace.toml"
    inputs = MarkdownInputs(trace_map=trace, trace_map_name="«ventas.toml»")
    raw = (
        f"markdown.trace_map no se puede leer ({trace}): Expected '=' (line 1); "
        f"markdown.trace_map ({trace.name}) no es válido: tables.x: campo desconocido; otro /srv/datos/a/b.json"
    )

    message = public_message(raw, inputs)

    assert str(tmp_path) not in message and tmp_path.as_posix() not in message
    assert "plantilla_trace" not in message and "/srv/datos" not in message
    assert "«ventas.toml»" in message and "campo desconocido" in message
    assert message.startswith("El mapa de trazabilidad")


@pytest.mark.parametrize(
    "kept",
    [
        "src/ventas/pedidos.py",
        "https://jira.example.com/browse/VEN-7",
        'routines."PROCEDURE:ventas/alta"',
        "C:archivo",
    ],
)
def test_public_message_keeps_relative_paths_urls_and_keys(kept: str) -> None:
    message = public_message(
        f"markdown.trace_map (m.toml) no es válido: {kept}: campos desconocidos x", MarkdownInputs()
    )

    assert kept in message
    assert "<fichero>" not in message


@pytest.mark.parametrize("path", ["/srv/datos/a.toml", "C:\\Datos\\ubw\\a.toml", "C:/Datos/ubw/a.toml"])
def test_public_message_hides_absolute_paths_after_space_quote_or_paren(path: str) -> None:
    for wrapped in (f"x {path}", f"x '{path}'", f"x ({path})"):
        message = public_message(f"markdown.previous: {wrapped}", MarkdownInputs())

        assert path not in message and "<fichero>" in message


def test_public_message_is_bounded() -> None:
    assert len(public_message("markdown.trace_map: " + "x" * 5000, MarkdownInputs())) == 2000


def test_markdown_input_error_follows_the_cause_chain() -> None:
    from util_bbdd.exceptions import DocumentationConfigError

    try:
        try:
            raise DocumentationConfigError("markdown.previous: la generación anterior es de otro motor ('mysql')")
        except DocumentationConfigError as inner:
            raise RuntimeError("envoltorio") from inner
    except RuntimeError as exc:
        error = markdown_input_error(exc, MarkdownInputs())

    assert isinstance(error, MarkdownInputError)
    assert error.kind == "previous"
    assert error.message.startswith("La documentación anterior")
    assert markdown_input_error(ValueError("otra cosa"), MarkdownInputs()) is None


def test_markdown_only_does_not_need_graphviz(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = tmp_path / "bd.db"
    con = sqlite3.connect(database)
    con.executescript("CREATE TABLE a (id INTEGER PRIMARY KEY); CREATE TABLE b (id INTEGER, a_id REFERENCES a(id));")
    con.close()
    monkeypatch.setattr(doc.shutil, "which", lambda _: None)  # sin ``dot``
    outputs = tmp_path / "outputs"

    summary = generate_documentation(
        "sqlite",
        {"database": str(database)},
        schema=None,
        options=DocumentationOptions(formats=("markdown",), graphs=True),
        outputs_dir=outputs,
        work_dir=tmp_path / "work",
        name="documentacion",
    )

    assert summary["formats"] == {"markdown": "markdown/documentacion/docs/index.md"}
    assert (outputs / "markdown/documentacion/mkdocs.yml").is_file()
    with pytest.raises(doc.GraphvizMissingError):
        generate_documentation(
            "sqlite",
            {"database": str(database)},
            schema=None,
            options=DocumentationOptions(formats=("markdown", "html"), graphs=True),
            outputs_dir=outputs,
            work_dir=tmp_path / "work",
            name="documentacion",
        )


# --- mapas de trazabilidad (subida) ------------------------------------------------------------------------------


def test_trace_kind_and_suffix() -> None:
    assert kind_for("Mapa.TOML") == ("trace", False)
    assert kind_for("mapa.json") == ("trace", False)
    assert stored_suffix("trace", "Mapa.JSON") == "json"
    assert stored_suffix("trace", "mapa.toml") == "toml"
    assert stored_suffix("word", "x.dotx") == "docx"


@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        ("m.toml", b"[tables\n", "no se puede leer"),
        ("m.json", b"{", "no se puede leer"),
        ("m.json", b"[]", "debe ser un objeto"),
        ("m.toml", "a = 'ñ'".encode("latin-1"), "UTF-8"),
        ("m.toml", b"#" * 1_000_001, "superar"),
    ],
    ids=["toml", "json", "no-object", "latin-1", "too-large"],  # sin ids, el de 1 MB no cabe en PYTEST_CURRENT_TEST
)
def test_trace_check_rejects(tmp_path: Path, name: str, content: bytes, message: str) -> None:
    path = tmp_path / name
    path.write_bytes(content)

    with pytest.raises(TemplateContentError, match=message):
        check_template(path, "trace", max_uncompressed=0)


def test_trace_base_template_is_valid(tmp_path: Path) -> None:
    path = tmp_path / "base.toml"
    path.write_bytes(base_template("trace"))

    info = check_template(path, "trace", max_uncompressed=0)

    assert (info.table_styles, info.table_style) == ([], None)
