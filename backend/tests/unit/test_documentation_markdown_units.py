"""Documentación Markdown (util_bbdd 5.3.0): bloque ``imprimir["markdown"]``, condición de Graphviz, mensajes sin rutas
del servidor y comprobación de los mapas de trazabilidad al subirlos."""

from __future__ import annotations

import io
import sqlite3
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from app.api.v1.runs import MERMAID_MISSING_WARNING, _archive_extras
from app.core.config import Settings
from app.db.models import Run
from app.domain.templates.errors import TemplateContentError
from app.domain.templates.files import base_template, check_template, kind_for, stored_suffix
from app.integrations.util_bbdd import documentation as doc
from app.integrations.util_bbdd.documentation import (
    MARKDOWN_MERMAID_ARTIFACT,
    MERMAID_JS_REF,
    DocumentationOptions,
    MarkdownInputError,
    MarkdownInputs,
    build_imprimir,
    generate_documentation,
    markdown_input_error,
    public_message,
)
from app.workspace.layout import zip_stream


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


def test_imprimir_markdown_block_with_referenced_mermaid() -> None:
    options = DocumentationOptions(formats=("markdown",))

    block = build_imprimir(options, markdown=MarkdownInputs(mermaid_js_ref=MERMAID_JS_REF))["markdown"]

    assert block == {"max_diagram_depth": 2, "mermaid_js_ref": "assets/javascripts/mermaid.min.js"}
    assert MARKDOWN_MERMAID_ARTIFACT == "outputs/markdown/documentacion/docs/assets/javascripts/mermaid.min.js"


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


# --- Mermaid referenciado en el ZIP (G50) --------------------------------------------------------------------------


def _run(manifest: dict[str, object] | None) -> Run:
    return cast(Run, SimpleNamespace(manifest=manifest))


def _settings(mermaid: Path | None) -> Settings:
    return cast(Settings, SimpleNamespace(mermaid_js=mermaid))


REFERENCED = {"markdown_mermaid": {"mode": "referenced", "path": "x", "sha256": "0"}}


def test_archive_adds_the_server_mermaid_only_when_referenced(tmp_path: Path) -> None:
    mermaid = tmp_path / "mermaid.min.js"
    mermaid.write_text("window.mermaid = {};", encoding="utf-8")
    pages = ["outputs/markdown/documentacion/docs/index.md"]

    assert _archive_extras(_run(REFERENCED), None, pages, _settings(mermaid)) == (
        [(MARKDOWN_MERMAID_ARTIFACT, mermaid)],
        False,
    )
    assert _archive_extras(_run(REFERENCED), "markdown", pages, _settings(mermaid))[0]
    # Otros formatos, ejecuciones sin el modo (anteriores a la 1.13.0) o con su copia registrada: nada que añadir.
    for fmt in ("word", "excel", "html"):
        assert _archive_extras(_run(REFERENCED), fmt, pages, _settings(mermaid)) == ([], False)
    assert _archive_extras(_run({}), None, pages, _settings(mermaid)) == ([], False)
    assert _archive_extras(_run(None), None, pages, _settings(mermaid)) == ([], False)
    copied = [*pages, MARKDOWN_MERMAID_ARTIFACT]
    assert _archive_extras(_run(REFERENCED), None, copied, _settings(mermaid)) == ([], False)


def test_archive_reports_a_missing_server_mermaid(tmp_path: Path) -> None:
    assert _archive_extras(_run(REFERENCED), None, [], _settings(None)) == ([], True)
    assert _archive_extras(_run(REFERENCED), "markdown", [], _settings(tmp_path / "falta.js")) == ([], True)
    assert MERMAID_MISSING_WARNING.isascii()


def test_zip_stream_writes_extras_after_the_artifacts(tmp_path: Path) -> None:
    (tmp_path / "outputs").mkdir()
    (tmp_path / "outputs" / "a.txt").write_text("a", encoding="utf-8")
    extra = tmp_path.parent / f"{tmp_path.name}-extra.js"
    extra.write_text("js", encoding="utf-8")

    data = b"".join(zip_stream(tmp_path, ["outputs/a.txt"], prefix="run", extras=[("outputs/b/c.js", extra)]))

    with zipfile.ZipFile(io.BytesIO(data)) as zipped:
        assert zipped.namelist() == ["run/outputs/a.txt", "run/outputs/b/c.js"]
        assert zipped.read("run/outputs/b/c.js") == b"js"
