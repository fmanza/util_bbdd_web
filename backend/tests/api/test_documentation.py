"""Fase 5: documentación (Word, Excel, HTML) y grafos de relaciones con util_bbdd real sobre SQLite, más el sitio
HTML servido por URL firmada (ADR-007). Necesita Graphviz (``dot``) para los grafos; el CI lo instala."""

from __future__ import annotations

import shutil
import sqlite3
import time
import zipfile
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import site_token
from app.db.models import User
from app.jobs.worker import Worker
from app.workspace.layout import run_dir
from tests.api.test_projects import new_project
from tests.api.test_runs import wait_for, worker  # noqa: F401  (fixture)

needs_dot = pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz (dot) no está instalado")

TIENDA = """
CREATE TABLE clientes (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL);
CREATE TABLE productos (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, precio REAL);
CREATE TABLE pedidos (
    id INTEGER PRIMARY KEY,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    fecha TEXT
);
CREATE TABLE lineas (
    pedido_id INTEGER NOT NULL REFERENCES pedidos(id),
    producto_id INTEGER NOT NULL REFERENCES productos(id),
    cantidad INTEGER,
    PRIMARY KEY (pedido_id, producto_id)
);
CREATE INDEX ix_pedidos_cliente ON pedidos (cliente_id);
CREATE VIEW v_pedidos AS SELECT p.id, c.nombre FROM pedidos p JOIN clientes c ON c.id = p.cliente_id;
"""


@pytest.fixture
def project(user_client: TestClient, settings: Settings) -> dict[str, object]:
    con = sqlite3.connect(settings.files_dir / "tienda.db")
    con.executescript(TIENDA)
    con.close()
    sueltas = sqlite3.connect(settings.files_dir / "sueltas.db")
    sueltas.execute("CREATE TABLE a (id INTEGER PRIMARY KEY)")
    sueltas.close()
    body = new_project(user_client)
    for name, database, alias in [("Tienda", "tienda.db", "tienda"), ("Sueltas", "sueltas.db", "sueltas")]:
        connection_id = user_client.post(
            "/api/v1/connections", json={"name": name, "db_type": "sqlite", "params": {"database": database}}
        ).json()["id"]
        response = user_client.post(
            f"/api/v1/projects/{body['id']}/connections", json={"connection_id": connection_id, "alias": alias}
        )
        assert response.status_code == 201, response.text
    return body


def launch(client: TestClient, project_id: object, operation: str, **params: object) -> str:
    response = client.post(f"/api/v1/projects/{project_id}/runs", json={"operation": operation, "params": params})
    assert response.status_code == 202, response.text
    return str(response.json()["id"])


def anonymous(client: TestClient) -> TestClient:
    return TestClient(client.app, base_url="https://testserver")


# --- catálogo ----------------------------------------------------------------------------------------------------


def test_catalog_exposes_groups_and_options(user_client: TestClient) -> None:
    operations = {o["name"]: o for o in user_client.get("/api/v1/operations").json()}
    doc = {p["name"]: p for p in operations["documentation"]["params"]}
    graph = {p["name"]: p for p in operations["relationship_graph"]["params"]}

    assert doc["connection"]["type"] == "connection"
    assert doc["schema"]["required"] is False
    assert (doc["word"]["group"], doc["word"]["default"]) == ("formats", True)
    assert doc["graph_direction"]["options"] == ["both", "outgoing", "incoming"]
    assert graph["format"]["options"] == ["svg", "png"]
    assert graph["table"]["group"] is None


def test_documentation_needs_a_format(user_client: TestClient, project: dict[str, object]) -> None:
    response = user_client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={
            "operation": "documentation",
            "params": {"connection": "tienda", "word": False, "excel": False, "html": False},
        },
    )

    assert response.status_code == 422
    assert "al menos un formato" in response.text


# --- documentación -----------------------------------------------------------------------------------------------


@needs_dot
def test_documentation_generates_word_excel_and_site(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
) -> None:
    run_id = launch(user_client, project["id"], "documentation", connection="tienda", table_ddl=True)
    run = wait_for(worker, db, run_id, timeout=180)

    assert run.status == "succeeded", (run.error_code, run.error_message)
    detail = user_client.get(f"/api/v1/runs/{run_id}").json()
    paths = {a["path"]: a for a in detail["artifacts"]}
    word = [p for p in paths if p.startswith("outputs/word/") and p.endswith(".docx")]
    excel = [p for p in paths if p.startswith("outputs/excel/") and p.endswith(".xlsx")]
    assert word and excel
    directory = run_dir(settings.workspace_dir, str(run.workspace_path))
    with zipfile.ZipFile(directory / word[0]) as docx:
        assert "pedidos" in docx.read("word/document.xml").decode("utf-8")
    with zipfile.ZipFile(directory / excel[0]) as xlsx:
        assert "xl/workbook.xml" in xlsx.namelist()
    assert "outputs/html/documentacion/index.html" in paths
    assert any(p.startswith("outputs/html/documentacion/graphs/") and p.endswith(".svg") for p in paths)
    assert not (directory / "work").exists()
    assert detail["site_url"].startswith(f"/api/v1/runs/{run_id}/site/")
    assert detail["site_url"].endswith("/documentacion/index.html")
    log = (directory / "logs" / "run.log").read_text(encoding="utf-8")
    assert "Documentación generada" in log


@needs_dot
@pytest.mark.parametrize(("graph_columns", "shown"), [("relations_first", True), ("relations", False)])
def test_documentation_graph_columns(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
    graph_columns: str,
    shown: bool,
) -> None:
    """``clientes.nombre`` no participa en ninguna relación: solo sale en el diagrama si se piden más columnas."""
    run_id = launch(
        user_client, project["id"], "documentation", connection="tienda", word=False, excel=False,
        graph_columns=graph_columns,
    )  # fmt: skip
    run = wait_for(worker, db, run_id, timeout=180)

    assert run.status == "succeeded", (run.error_code, run.error_message)
    graphs = run_dir(settings.workspace_dir, str(run.workspace_path)) / "outputs" / "html" / "documentacion" / "graphs"
    svg = "".join(p.read_text(encoding="utf-8") for p in graphs.glob("*_clientes_*.svg"))
    assert ">[PK] id<" in svg
    assert (">nombre<" in svg) is shown


@needs_dot
def test_site_is_served_by_signed_url_only(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
    make_user: Callable[..., User],
) -> None:
    run_id = launch(user_client, project["id"], "documentation", connection="tienda", word=False, excel=False)
    run = wait_for(worker, db, run_id, timeout=180)
    assert run.status == "succeeded", (run.error_code, run.error_message)
    site_url: str = user_client.get(f"/api/v1/runs/{run_id}").json()["site_url"]
    base = site_url.removesuffix("index.html")
    browser = anonymous(user_client)  # el iframe con origen opaco no envía la cookie

    index = browser.get(site_url)
    script = browser.get(base + "assets/sql-highlight.js")
    detail = browser.get(base + "tables/pedidos.html")

    assert index.status_code == 200
    assert index.headers["content-type"].startswith("text/html")
    csp = index.headers["content-security-policy"]
    assert csp.startswith("sandbox allow-scripts") and "allow-same-origin" not in csp
    assert "connect-src 'none'" in csp
    assert "frame-src 'self'" in csp and "frame-ancestors 'self'" in csp
    assert index.headers["referrer-policy"] == "no-referrer"
    assert index.headers["x-content-type-options"] == "nosniff"
    assert script.status_code == 200 and script.headers["content-type"].startswith("text/javascript")
    # El detalle se carga en el iframe del índice (origen opaco): sin frame-ancestors, que lo bloquearía.
    assert detail.status_code == 200
    assert detail.headers["content-security-policy"].startswith("sandbox allow-scripts")
    assert "frame-ancestors" not in detail.headers["content-security-policy"]
    assert detail.headers["referrer-policy"] == "no-referrer"
    # Hotfix 2026-10-25: las pestañas que abre el sitio heredan el sandbox; con COOP distinto de unsafe-none, Chromium
    # las bloquea (ERR_BLOCKED_BY_RESPONSE). El resto de la aplicación sigue con same-origin.
    collection = browser.get(base + "collections/tables_all.html")
    assert collection.status_code == 200
    for response in (index, detail, collection):
        assert response.headers["cross-origin-opener-policy"] == "unsafe-none"
    assert user_client.get(f"/api/v1/runs/{run_id}").headers["cross-origin-opener-policy"] == "same-origin"

    token = site_url.split("/")[6]
    forged = token[:-1] + ("0" if token[-1] != "0" else "1")
    assert browser.get(site_url.replace(token, forged)).status_code == 404
    assert browser.get(base + "../../../run.json").status_code == 404
    assert browser.get(base + "no-existe.html").status_code == 404
    assert browser.get(f"/api/v1/runs/{run_id}/site/{token}/../../logs/run.log").status_code == 404
    other_run = launch(user_client, project["id"], "noop", steps=1, step_seconds=0)
    assert browser.get(site_url.replace(run_id, other_run)).status_code == 404

    user_id = int(token.split(".")[0])
    expired = site_token(settings, run_id=run_id, user_id=user_id, expires=int(time.time()) - 1)
    assert browser.get(site_url.replace(token, expired)).status_code == 404
    outsider = make_user("olga")
    outsider_token = site_token(settings, run_id=run_id, user_id=outsider.id, expires=int(time.time()) + 60)
    assert browser.get(site_url.replace(token, outsider_token)).status_code == 404

    db.execute(update(User).where(User.id == user_id).values(is_active=False))
    db.commit()
    assert browser.get(site_url).status_code == 404


def test_site_rejects_malformed_tokens(user_client: TestClient, project: dict[str, object]) -> None:
    run_id = launch(user_client, project["id"], "noop", steps=1, step_seconds=0)
    browser = anonymous(user_client)

    for token in ["x", "1.9999999999.x", "a.b.c", "1.2", "-1.9999999999.abc"]:
        assert browser.get(f"/api/v1/runs/{run_id}/site/{token}/index.html").status_code == 404, token


def test_schema_param_keeps_its_alias(user_client: TestClient, project: dict[str, object]) -> None:
    run_id = launch(user_client, project["id"], "documentation", connection="tienda", schema="main", html=False)

    assert user_client.get(f"/api/v1/runs/{run_id}").json()["params"]["schema"] == "main"


# --- grafos ------------------------------------------------------------------------------------------------------


def _graph(
    client: TestClient, project: dict[str, object], job_worker: Worker, db: Session, **params: Any
) -> tuple[Any, list[str]]:
    run_id = launch(client, project["id"], "relationship_graph", **params)
    run = wait_for(job_worker, db, run_id, timeout=120)
    paths = [a["path"] for a in client.get(f"/api/v1/runs/{run_id}").json()["artifacts"]]
    return run, [p for p in paths if p.startswith("outputs/graphs/")]


@needs_dot
def test_graph_of_one_table_and_of_all(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
) -> None:
    one, one_files = _graph(user_client, project, worker, db, connection="tienda", table="pedidos")
    every, all_files = _graph(user_client, project, worker, db, connection="tienda", format="png")

    assert one.status == "succeeded", (one.error_code, one.error_message)
    assert one_files and all(p.endswith(".svg") for p in one_files)
    assert every.status == "succeeded", (every.error_code, every.error_message)
    assert len(all_files) >= 3 and all(p.endswith(".png") for p in all_files)


@needs_dot
@pytest.mark.parametrize(
    ("column_mode", "shown"), [("relations_first", True), ("relations", False), ("all", True), ("compact", False)]
)
def test_graph_column_modes(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
    column_mode: str,
    shown: bool,
) -> None:
    """``clientes.nombre`` no participa en ninguna relación: sale con «primero las de relación» y con «todas»."""
    run, files = _graph(
        user_client, project, worker, db, connection="tienda", table="clientes", column_mode=column_mode
    )

    assert run.status == "succeeded", (run.error_code, run.error_message)
    directory = run_dir(settings.workspace_dir, str(run.workspace_path))
    svg = "".join((directory / f).read_text(encoding="utf-8") for f in files)
    assert ">clientes<" in svg
    assert (">nombre<" in svg) is shown


@needs_dot
def test_graph_errors_are_sanitized(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
) -> None:
    missing, _ = _graph(user_client, project, worker, db, connection="tienda", table="no_existe")
    lonely, _ = _graph(user_client, project, worker, db, connection="sueltas")

    assert (missing.status, missing.error_code) == ("failed", "invalid_params")
    assert "no_existe" in str(missing.error_message)
    assert (lonely.status, lonely.error_code) == ("failed", "no_relations")
