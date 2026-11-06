"""Documentación Markdown (util_bbdd 5.3.0) con util_bbdd real sobre SQLite: carpeta completa, Mermaid local, mapa de
trazabilidad (plantilla ``trace``) y cambios respecto de una documentación anterior en el visor de diferencias.

No necesita Graphviz: los diagramas del Markdown son de Mermaid.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.jobs.worker import Worker
from app.workspace.layout import run_dir
from tests.api.test_documentation import launch, project  # noqa: F401  (fixture)
from tests.api.test_runs import wait_for, worker  # noqa: F401  (fixture)
from tests.api.test_templates import project_url, upload

ROOT = "outputs/markdown/documentacion/"
ONLY_MARKDOWN: dict[str, Any] = {"connection": "tienda", "word": False, "excel": False, "html": False, "markdown": True}
TRACE_OK = b'version = 1\n\n[tables."pedidos"]\ncode = ["src/ventas/pedidos.py#Pedido"]\nrequirements = ["REQ-1"]\n'
#: Sintaxis correcta (pasa la subida) pero campos que no existen: util_bbdd lo rechaza al generar, con todos los errores.
TRACE_BAD = b'[tables."pedidos"]\nrequirement = ["REQ-1"]\n\n[views."v_pedidos"]\ncodigo = ["x"]\n'


def _trace(client: TestClient, project_id: object, content: bytes, filename: str = "mapa.toml") -> str:
    response = upload(client, project_url(project_id), filename, content)
    assert response.status_code == 201, response.text
    assert response.json()["kind"] == "trace"
    return str(response.json()["id"])


def _use_mermaid(monkeypatch: pytest.MonkeyPatch, settings: Settings, tmp_path: Path) -> Path:
    """``UBW_MERMAID_JS`` para el worker (el subproceso lo lee del entorno) y para la API (``settings`` en caché)."""
    mermaid_js = tmp_path / "mermaid.min.js"
    mermaid_js.write_text("window.mermaid = {};", encoding="utf-8")
    monkeypatch.setenv("UBW_MERMAID_JS", str(mermaid_js))
    monkeypatch.setattr(settings, "mermaid_js", mermaid_js)
    return mermaid_js


def _paths(client: TestClient, run_id: str) -> dict[str, dict[str, Any]]:
    return {a["path"]: a for a in client.get(f"/api/v1/runs/{run_id}").json()["artifacts"]}


def test_catalog_exposes_markdown_params(user_client: TestClient) -> None:
    operations = {o["name"]: o for o in user_client.get("/api/v1/operations").json()}
    doc = {p["name"]: p for p in operations["documentation"]["params"]}

    assert (doc["markdown"]["group"], doc["markdown"]["default"]) == ("formats", False)
    assert doc["markdown_site_name"]["requires"] == "markdown"
    assert (doc["markdown_diagram_depth"]["minimum"], doc["markdown_diagram_depth"]["maximum"]) == (1, 3)
    assert (doc["trace_map"]["type"], doc["trace_map"]["template_kind"]) == ("template", "trace")
    assert (doc["markdown_previous_run"]["type"], doc["markdown_previous_run"]["run_operation"]) == (
        "run",
        "documentation",
    )
    assert doc["word"]["requires"] is None


def test_markdown_generates_the_whole_folder(
    user_client: TestClient,
    project: dict[str, object],  # noqa: F811
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mermaid_js = _use_mermaid(monkeypatch, settings, tmp_path)

    run_id = launch(user_client, project["id"], "documentation", **ONLY_MARKDOWN, markdown_site_name="Tienda")
    run = wait_for(worker, db, run_id, timeout=180)

    assert run.status == "succeeded", (run.error_code, run.error_message)
    paths = _paths(user_client, run_id)
    for name in ("docs/index.md", "docs/catalog.json", "docs/llms.txt", "mkdocs.yml", "manifest.json"):
        assert ROOT + name in paths, name
    assert paths[ROOT + "docs/index.md"]["kind"] == "markdown"
    assert any(p.startswith(ROOT + "docs/tables/") and p.endswith("pedidos.md") for p in paths)
    # G50 (util_bbdd 5.4.0): Mermaid referenciado, no copiado en la ejecución.
    assert ROOT + "docs/assets/javascripts/mermaid.min.js" not in paths
    directory = run_dir(settings.workspace_dir, str(run.workspace_path))
    assert not (directory / ROOT / "docs/assets/javascripts/mermaid.min.js").exists()
    manifest = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    assert manifest["markdown_mermaid"] == {
        "mode": "referenced",
        "path": ROOT + "docs/assets/javascripts/mermaid.min.js",
        "sha256": hashlib.sha256(mermaid_js.read_bytes()).hexdigest(),
    }
    mkdocs = (directory / ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    assert "extra_javascript" in mkdocs and "assets/javascripts/mermaid.min.js" in mkdocs
    assert "Tienda" in mkdocs
    assert "unpkg" not in mkdocs
    pedidos = next(p for p in paths if p.startswith(ROOT + "docs/tables/") and p.endswith("pedidos.md"))
    assert "erDiagram" in (directory / pedidos).read_text(encoding="utf-8")
    assert not (directory / "work").exists()
    detail = user_client.get(f"/api/v1/runs/{run_id}").json()
    assert detail["has_diff"] is False
    assert detail["site_url"] is None
    assert detail["warnings"] == []

    archive = user_client.get(f"/api/v1/runs/{run_id}/archive")
    assert archive.status_code == 200
    assert "x-ubw-warning" not in archive.headers
    with zipfile.ZipFile(io.BytesIO(archive.content)) as zipped:
        names = zipped.namelist()
        bundled = [n for n in names if n.endswith("markdown/documentacion/docs/assets/javascripts/mermaid.min.js")]
        # El ZIP lleva el Mermaid del servidor (una sola vez), así que la carpeta se publica sin Internet.
        assert len(bundled) == 1 and zipped.read(bundled[0]) == mermaid_js.read_bytes()
    assert any(n.endswith("markdown/documentacion/docs/index.md") for n in names)
    assert any(n.endswith("markdown/documentacion/mkdocs.yml") for n in names)

    # Si el Mermaid del servidor desaparece, el ZIP sale sin él y lo avisa (el tema lo cargará de Internet).
    monkeypatch.setattr(settings, "mermaid_js", tmp_path / "ya-no-esta.js")
    without = user_client.get(f"/api/v1/runs/{run_id}/archive", params={"format": "markdown"})
    assert without.status_code == 200 and "Mermaid" in without.headers["x-ubw-warning"]
    with zipfile.ZipFile(io.BytesIO(without.content)) as zipped:
        assert not any(n.endswith("mermaid.min.js") for n in zipped.namelist())


def test_markdown_without_mermaid_js_warns(
    user_client: TestClient,
    project: dict[str, object],  # noqa: F811
    worker: Worker,  # noqa: F811
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("UBW_MERMAID_JS", str(tmp_path / "no-existe.js"))

    run_id = launch(user_client, project["id"], "documentation", **ONLY_MARKDOWN)
    run = wait_for(worker, db, run_id, timeout=180)

    assert run.status == "succeeded", (run.error_code, run.error_message)
    detail = user_client.get(f"/api/v1/runs/{run_id}").json()
    assert any("Mermaid" in w for w in detail["warnings"])
    assert list(detail["warnings_by_format"]) == ["markdown"]
    assert detail["warnings_by_format"]["markdown"] == [w for w in detail["warnings"] if "Mermaid" in w]


#: Carpetas de páginas de la documentación Markdown de util_bbdd 5.3.0 de las que depende el árbol del visor de la web
#: (``frontend/src/features/runs/documentation/markdownNav.ts``). Mientras G51 siga abierto, este test avisa si cambian.
MARKDOWN_SECTIONS = {"tables", "views", "routines", "database"}


def test_documentation_archive_by_format_preview_rules_and_page_layout(
    user_client: TestClient,
    project: dict[str, object],  # noqa: F811
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_mermaid(monkeypatch, settings, tmp_path)
    params = {**ONLY_MARKDOWN, "excel": True, "html": True, "graphs": False}

    run_id = launch(user_client, project["id"], "documentation", **params)
    run = wait_for(worker, db, run_id, timeout=180)

    assert run.status == "succeeded", (run.error_code, run.error_message)
    detail = user_client.get(f"/api/v1/runs/{run_id}").json()
    assert detail["warnings_by_format"] == {} and detail["templates_applied"] == {}
    paths = {a["path"]: a for a in detail["artifacts"]}

    # Vista previa: solo las páginas .md de la carpeta Markdown (los auxiliares se descargan).
    assert paths[ROOT + "docs/index.md"]["previewable"] is True
    for name in ("docs/catalog.json", "docs/llms.txt", "mkdocs.yml"):
        assert paths[ROOT + name]["kind"] == "markdown" and paths[ROOT + name]["previewable"] is False, name
    catalog = paths[ROOT + "docs/catalog.json"]["id"]
    assert user_client.get(f"/api/v1/runs/{run_id}/artifacts/{catalog}/preview").status_code == 415

    # Contrato con util_bbdd (T2, G51): las páginas están en la raíz de docs/ o en una de las secciones conocidas.
    pages = [p.removeprefix(ROOT + "docs/") for p in paths if p.startswith(ROOT + "docs/") and p.endswith(".md")]
    sections = {page.split("/")[0] for page in pages if "/" in page}
    assert sections <= MARKDOWN_SECTIONS, sections
    assert {"tables", "views"} <= sections
    assert "index.md" in pages and "tables/index.md" in pages and "views/index.md" in pages
    assert any(page.startswith("tables/index-") for page in pages)
    assert all(page.count("/") <= 1 for page in pages)

    def archive(fmt: str) -> tuple[int, str, list[str]]:
        response = user_client.get(f"/api/v1/runs/{run_id}/archive", params={"format": fmt})
        if response.status_code != 200:
            return response.status_code, "", []
        with zipfile.ZipFile(io.BytesIO(response.content)) as zipped:
            return 200, response.headers["content-disposition"], zipped.namelist()

    status, disposition, names = archive("markdown")
    assert status == 200 and disposition.endswith('_markdown.zip"')
    assert names and all("/outputs/markdown/" in n for n in names)
    assert any(n.endswith("markdown/documentacion/mkdocs.yml") for n in names)
    assert any(n.endswith("docs/assets/javascripts/mermaid.min.js") for n in names)
    status, _, names = archive("html")
    assert status == 200 and names and all("/outputs/html/" in n for n in names)
    assert any(n.endswith("outputs/html/documentacion/index.html") for n in names)
    status, _, names = archive("excel")
    assert status == 200 and len(names) == 1 and names[0].endswith(".xlsx")
    assert archive("word")[0] == 404  # formato no pedido
    assert archive("pdf")[0] == 422
    complete = user_client.get(f"/api/v1/runs/{run_id}/archive")
    with zipfile.ZipFile(io.BytesIO(complete.content)) as zipped:
        assert any(n.endswith("/run.json") for n in zipped.namelist())


def test_markdown_options_are_dropped_without_markdown(
    user_client: TestClient,
    project: dict[str, object],  # noqa: F811
) -> None:
    trace_id = _trace(user_client, project["id"], TRACE_OK)
    run_id = launch(
        user_client, project["id"], "documentation", connection="tienda", markdown_site_name="X", trace_map=trace_id
    )

    params = user_client.get(f"/api/v1/runs/{run_id}").json()["params"]
    assert params["markdown"] is False
    assert params["markdown_site_name"] is None
    assert params["trace_map"] is None


# --- mapa de trazabilidad ----------------------------------------------------------------------------------------


def test_trace_map_upload_checks_syntax_and_size(user_client: TestClient, project: dict[str, object]) -> None:  # noqa: F811
    url = project_url(project["id"])

    assert upload(user_client, url, "mapa.toml", b"[tables\n").status_code == 422
    assert upload(user_client, url, "mapa.json", b"[1, 2]").status_code == 422
    assert upload(user_client, url, "mapa.toml", "a = 1\n".encode("utf-16")).status_code == 422
    assert upload(user_client, url, "mapa.toml", b"# " + b"x" * 1_000_001).status_code == 413
    response = upload(user_client, url, "Mapa.JSON", json.dumps({"tables": {"pedidos": {"code": ["a.py"]}}}).encode())
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["kind"], body["table_styles"], body["table_style"]) == ("trace", [], None)
    download = user_client.get(f"{url}/{body['id']}/file")
    assert download.status_code == 200
    assert 'filename="Mapa.json"' in download.headers["content-disposition"]


def test_trace_map_base_is_a_valid_example(user_client: TestClient, project: dict[str, object]) -> None:  # noqa: F811
    base = user_client.get("/api/v1/document-templates/base/trace")

    assert base.status_code == 200
    assert "mapa_trazabilidad.toml" in base.headers["content-disposition"]
    assert upload(user_client, project_url(project["id"]), "ejemplo.toml", base.content).status_code == 201


def test_trace_map_applies_to_markdown(
    user_client: TestClient,
    project: dict[str, object],  # noqa: F811
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
) -> None:
    trace_id = _trace(user_client, project["id"], TRACE_OK)

    run_id = launch(user_client, project["id"], "documentation", **ONLY_MARKDOWN, trace_map=trace_id)
    run = wait_for(worker, db, run_id, timeout=180)

    assert run.status == "succeeded", (run.error_code, run.error_message)
    paths = _paths(user_client, run_id)
    assert ROOT + "docs/traceability.md" in paths
    directory = run_dir(settings.workspace_dir, str(run.workspace_path))
    assert "REQ-1" in (directory / ROOT / "docs/traceability.md").read_text(encoding="utf-8")
    templates = json.loads((directory / "run.json").read_text(encoding="utf-8")).get("templates", [])
    assert any(t["kind"] == "trace" and t["applied"] is True for t in templates)


def test_invalid_trace_map_fails_with_every_error_and_no_paths(
    user_client: TestClient,
    project: dict[str, object],  # noqa: F811
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
) -> None:
    trace_id = _trace(user_client, project["id"], TRACE_BAD, filename="ventas.toml")

    run_id = launch(user_client, project["id"], "documentation", **ONLY_MARKDOWN, trace_map=trace_id)
    run = wait_for(worker, db, run_id, timeout=180)

    assert run.status == "failed"
    assert run.error_code == "invalid_trace_map"
    message = str(run.error_message)
    assert "requirement" in message and "codigo" in message
    assert "ventas.toml" in message
    for secret in (str(settings.workspace_dir), settings.workspace_dir.as_posix(), "inputs", "plantilla_trace"):
        assert secret not in message
    directory = run_dir(settings.workspace_dir, str(run.workspace_path))
    assert str(directory) not in (directory / "logs" / "run.log").read_text(encoding="utf-8")


def test_trace_template_in_use_and_wrong_kind(
    user_client: TestClient,
    project: dict[str, object],  # noqa: F811
) -> None:
    trace_id = _trace(user_client, project["id"], TRACE_OK)
    # Un mapa no sirve como plantilla Word.
    response = user_client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"operation": "documentation", "params": {"connection": "tienda", "word_template": trace_id}},
    )
    assert response.status_code == 422


# --- documentación anterior --------------------------------------------------------------------------------------


def test_previous_documentation_feeds_the_diff_viewer(
    user_client: TestClient,
    project: dict[str, object],  # noqa: F811
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
) -> None:
    first = launch(user_client, project["id"], "documentation", **ONLY_MARKDOWN)
    assert wait_for(worker, db, first, timeout=180).status == "succeeded"
    tienda = settings.files_dir / "tienda.db"
    import sqlite3

    con = sqlite3.connect(tienda)
    con.executescript("CREATE TABLE devoluciones (id INTEGER PRIMARY KEY, pedido_id INTEGER REFERENCES pedidos(id));")
    con.close()

    second = launch(user_client, project["id"], "documentation", **ONLY_MARKDOWN, markdown_previous_run=first)
    run = wait_for(worker, db, second, timeout=180)

    assert run.status == "succeeded", (run.error_code, run.error_message)
    paths = _paths(user_client, second)
    assert ROOT + "docs/changes.md" in paths and ROOT + "docs/changes.json" in paths
    directory = run_dir(settings.workspace_dir, str(run.workspace_path))
    assert (directory / "inputs" / "previous" / "catalog.json").is_file()
    detail = user_client.get(f"/api/v1/runs/{second}").json()
    assert detail["has_diff"] is True
    diff = user_client.get(f"/api/v1/runs/{second}/diff")
    assert diff.status_code == 200, diff.text
    assert diff.json()["has_differences"] is True
    assert "devoluciones" in diff.text
    # La primera no tiene anterior: sin visor.
    assert user_client.get(f"/api/v1/runs/{first}").json()["has_diff"] is False
    assert user_client.get(f"/api/v1/runs/{first}/diff").status_code == 404


def test_previous_documentation_purged_before_start_fails_the_run(
    user_client: TestClient,
    project: dict[str, object],  # noqa: F811
    worker: Worker,  # noqa: F811
    db: Session,
) -> None:
    first = launch(user_client, project["id"], "documentation", **ONLY_MARKDOWN)
    assert wait_for(worker, db, first, timeout=180).status == "succeeded"
    second = launch(user_client, project["id"], "documentation", **ONLY_MARKDOWN, markdown_previous_run=first)
    # Encolada (el worker no ha empezado): la anterior se purga antes de que arranque.
    assert user_client.delete(f"/api/v1/runs/{first}").status_code == 204

    run = wait_for(worker, db, second, timeout=180)

    assert run.status == "failed"
    assert run.error_code == "invalid_previous"
    assert "ya no está disponible" in str(run.error_message)


def test_previous_documentation_is_checked_on_launch(
    user_client: TestClient,
    project: dict[str, object],  # noqa: F811
    worker: Worker,  # noqa: F811
    db: Session,
) -> None:
    without_markdown = launch(user_client, project["id"], "documentation", connection="tienda", graphs=False)
    other_connection = launch(user_client, project["id"], "documentation", **{**ONLY_MARKDOWN, "connection": "sueltas"})
    for run_id in (without_markdown, other_connection):
        finished = wait_for(worker, db, run_id, timeout=180)
        assert finished.status == "succeeded", (finished.error_code, finished.error_message)

    def rejected(previous: str) -> str:
        response = user_client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"operation": "documentation", "params": {**ONLY_MARKDOWN, "markdown_previous_run": previous}},
        )
        assert response.status_code == 422, response.text
        return response.text

    assert "no tiene Markdown" in rejected(without_markdown)
    assert "otra conexión" in rejected(other_connection)
    assert "no existe en el proyecto" in rejected("01ARZ3NDEKTSV4RRFFQ69G5FAV")


def test_previous_documentation_of_another_project_is_not_revealed(
    user_client: TestClient,
    project: dict[str, object],  # noqa: F811
    worker: Worker,  # noqa: F811
    db: Session,
) -> None:
    from tests.api.test_projects import new_project

    first = launch(user_client, project["id"], "documentation", **ONLY_MARKDOWN)
    assert wait_for(worker, db, first, timeout=180).status == "succeeded"
    other = new_project(user_client, name="Otro")
    connection_id = user_client.post(
        "/api/v1/connections", json={"name": "Tienda 2", "db_type": "sqlite", "params": {"database": "tienda.db"}}
    ).json()["id"]
    user_client.post(
        f"/api/v1/projects/{other['id']}/connections", json={"connection_id": connection_id, "alias": "tienda"}
    )

    response = user_client.post(
        f"/api/v1/projects/{other['id']}/runs",
        json={"operation": "documentation", "params": {**ONLY_MARKDOWN, "markdown_previous_run": first}},
    )

    assert response.status_code == 422
    assert "no existe en el proyecto" in response.text
