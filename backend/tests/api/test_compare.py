"""Fase 6: comparación de esquemas con util_bbdd real sobre dos SQLite, visor del diff (``/diff``), evolución entre
comparaciones (``/diff/evolution``) e informes; ningún artefacto lleva rutas del servidor."""

from __future__ import annotations

import json
import sqlite3
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import User
from app.jobs.worker import Worker
from app.workspace.layout import run_dir
from tests.api.test_projects import login_as, new_project
from tests.api.test_runs import wait_for, worker  # noqa: F401  (fixture)

ORIGEN = """
CREATE TABLE clientes (id INTEGER PRIMARY KEY, nombre VARCHAR(80) NOT NULL, email VARCHAR(120));
CREATE TABLE pedidos (id INTEGER PRIMARY KEY, cliente_id INTEGER REFERENCES clientes(id), total NUMERIC(10, 2));
CREATE INDEX ix_pedidos_cliente ON pedidos (cliente_id);
CREATE TABLE facturas (id INTEGER PRIMARY KEY, pedido_id INTEGER);
CREATE VIEW v_clientes AS SELECT id, nombre FROM clientes;
"""
# Destino: falta ``facturas``, ``clientes.nombre`` admite nulos, falta ``email`` y el índice; sobra ``auditoria``;
# la vista cambia.
DESTINO = """
CREATE TABLE clientes (id INTEGER PRIMARY KEY, nombre VARCHAR(80));
CREATE TABLE pedidos (id INTEGER PRIMARY KEY, cliente_id INTEGER REFERENCES clientes(id), total NUMERIC(10, 2));
CREATE TABLE auditoria (id INTEGER PRIMARY KEY, evento TEXT);
CREATE VIEW v_clientes AS SELECT id FROM clientes;
"""


def _db(settings: Settings, name: str, script: str) -> None:
    path = settings.files_dir / name
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    con.executescript(script)
    con.close()


@pytest.fixture
def project(user_client: TestClient, settings: Settings) -> dict[str, object]:
    _db(settings, "origen.db", ORIGEN)
    _db(settings, "destino.db", DESTINO)
    body = new_project(user_client)
    for alias, database in [("origen", "origen.db"), ("destino", "destino.db")]:
        connection_id = user_client.post(
            "/api/v1/connections", json={"name": alias.title(), "db_type": "sqlite", "params": {"database": database}}
        ).json()["id"]
        response = user_client.post(
            f"/api/v1/projects/{body['id']}/connections", json={"connection_id": connection_id, "alias": alias}
        )
        assert response.status_code == 201, response.text
    return body


def compare(client: TestClient, project_id: object, **params: object) -> str:
    body = {"source_connection": "origen", "target_connection": "destino", **params}
    response = client.post(f"/api/v1/projects/{project_id}/runs", json={"operation": "compare", "params": body})
    assert response.status_code == 202, response.text
    return str(response.json()["id"])


def test_compare_params_are_validated(user_client: TestClient, project: dict[str, object]) -> None:
    url = f"/api/v1/projects/{project['id']}/runs"
    nothing = {"source_connection": "origen", "target_connection": "destino", "tables": False, "views": False}
    bad_schema = {"source_connection": "origen", "target_connection": "destino", "source_schema": "x'; --"}
    bad_dialect = {"source_connection": "origen", "target_connection": "destino", "sql_dialect": "db2"}

    for params in (nothing, bad_schema, bad_dialect, {"source_connection": "origen"}):
        assert user_client.post(url, json={"operation": "compare", "params": params}).status_code == 422, params


def test_compare_generates_diff_and_reports(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
) -> None:
    run_id = compare(user_client, project["id"], word=True)
    run = wait_for(worker, db, run_id, timeout=120)

    assert run.status == "succeeded", (run.error_code, run.error_message)
    diff = user_client.get(f"/api/v1/runs/{run_id}/diff")
    assert diff.status_code == 200, diff.text
    body = diff.json()
    assert body["source_label"] == "origen (sqlite)" and body["target_label"] == "destino (sqlite)"
    assert body["has_differences"] is True
    tables = {t["table_name"]: t for t in body["table_diffs"]}
    assert tables["facturas"]["status"] == "added"
    assert tables["auditoria"]["status"] == "removed"
    columns = {(c["column_name"], c["attribute"]) for c in tables["clientes"]["column_diffs"]}
    assert ("nombre", "nullable") in columns and ("email", "existence") in columns
    assert any(i["index_name"] == "ix_pedidos_cliente" for i in tables["pedidos"]["index_diffs"])
    views = {v["view_name"]: v for v in body["view_diffs"]}
    assert views["v_clientes"]["status"] == "modified"
    assert "nombre" in views["v_clientes"]["source_definition"]

    detail = user_client.get(f"/api/v1/runs/{run_id}").json()
    paths = {a["path"] for a in detail["artifacts"]}
    assert {
        "outputs/diff/schema_diff.json",
        "outputs/html/comparacion/index.html",
        "outputs/excel/comparacion.xlsx",
        "outputs/word/comparacion.docx",
        "outputs/markdown/comparacion.md",
        "outputs/sql/comparacion.sql",
    } <= paths
    assert detail["site_url"].endswith("/comparacion/index.html")
    # G25: el informe no carga nada externo y su sustituto de Mermaid se sirve con el sitio.
    assert "outputs/html/comparacion/assets/mermaid-stub.js" in paths
    report = (
        run_dir(settings.workspace_dir, str(run.workspace_path)) / "outputs/html/comparacion/index.html"
    ).read_text(encoding="utf-8")
    assert "https://" not in report.split("<main", 1)[0] + report.rsplit("</main>", 1)[-1]
    directory = run_dir(settings.workspace_dir, str(run.workspace_path))
    script = (directory / "outputs/sql/comparacion.sql").read_text(encoding="utf-8")
    assert "facturas" in script and "auditoria" in script

    # G23: ninguna salida lleva la ruta del servidor de los ficheros SQLite.
    server_path = str(Path(settings.files_dir).resolve())
    for path in paths:
        file = directory / path
        if file.suffix in {".docx", ".xlsx"}:
            with zipfile.ZipFile(file) as archive:
                content = "".join(archive.read(n).decode("utf-8", "replace") for n in archive.namelist())
        else:
            content = file.read_text(encoding="utf-8", errors="replace")
        for needle in (server_path, server_path.replace("\\", "/"), "sqlite:///"):
            assert needle not in content, (path, needle)


def test_identical_schemas_have_no_differences(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
) -> None:
    run_id = launch_same(user_client, project)
    run = wait_for(worker, db, run_id, timeout=120)

    assert run.status == "succeeded", (run.error_code, run.error_message)
    body = user_client.get(f"/api/v1/runs/{run_id}/diff").json()
    assert body["has_differences"] is False and body["summary"] == "Sin diferencias"


def launch_same(client: TestClient, project: dict[str, object]) -> str:
    return compare(client, project["id"], target_connection="origen", html=False, excel=False, sql=False)


def test_unknown_schema_fails_with_side(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
) -> None:
    run_id = compare(user_client, project["id"], target_schema="no_existe")
    run = wait_for(worker, db, run_id, timeout=120)

    assert (run.status, run.error_code) == ("failed", "invalid_params")
    assert run.error_message == "El schema «no_existe» no existe en el destino."


def test_unknown_alias_is_rejected_on_enqueue(user_client: TestClient, project: dict[str, object]) -> None:
    response = user_client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"operation": "compare", "params": {"source_connection": "origen", "target_connection": "otra"}},
    )

    assert response.status_code == 422
    assert "otra" in response.text


def test_evolution_between_two_comparisons(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
) -> None:
    before = compare(user_client, project["id"], html=False, excel=False, sql=False, markdown=False)
    wait_for(worker, db, before, timeout=120)
    # Se crea ``facturas`` en el destino (resuelta) y se borra ``pedidos.total`` (nueva diferencia).
    con = sqlite3.connect(settings.files_dir / "destino.db")
    con.executescript(
        "CREATE TABLE facturas (id INTEGER PRIMARY KEY, pedido_id INTEGER);ALTER TABLE pedidos DROP COLUMN total;"
    )
    con.close()
    after = compare(user_client, project["id"], html=False, excel=False, sql=False, markdown=False)
    wait_for(worker, db, after, timeout=120)

    response = user_client.get(f"/api/v1/runs/{after}/diff/evolution", params={"baseline": before})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["labels_match"] is True
    resolved = {(i["kind"], i["name"]) for i in body["resolved"]}
    new = {(i["kind"], i["table"], i["name"]) for i in body["new"]}
    persisting = {(i["kind"], i["name"]) for i in body["persisting"]}
    assert ("table", "facturas") in resolved
    assert ("column", "pedidos", "total") in new
    assert ("table", "auditoria") in persisting and ("view", "v_clientes") in persisting


def test_diff_endpoints_reject_other_runs_and_outsiders(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    make_user: Callable[..., User],
) -> None:
    noop = user_client.post(
        f"/api/v1/projects/{project['id']}/runs", json={"operation": "noop", "params": {"steps": 1, "step_seconds": 0}}
    ).json()["id"]
    wait_for(worker, db, noop)
    run_id = launch_same(user_client, project)
    wait_for(worker, db, run_id, timeout=120)
    outsider = login_as(user_client, make_user, "luis")

    assert user_client.get(f"/api/v1/runs/{noop}/diff").status_code == 404
    assert outsider.get(f"/api/v1/runs/{run_id}/diff").status_code == 404
    assert user_client.get(f"/api/v1/runs/{run_id}/diff/evolution", params={"baseline": noop}).status_code == 404
    assert user_client.get(f"/api/v1/runs/{run_id}/diff/evolution", params={"baseline": "nope"}).status_code == 404


def test_diff_too_large_is_413(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = launch_same(user_client, project)
    wait_for(worker, db, run_id, timeout=120)
    monkeypatch.setattr("app.domain.runs.diff.DIFF_MAX_BYTES", 10)

    assert user_client.get(f"/api/v1/runs/{run_id}/diff").status_code == 413


def test_purged_comparison_has_no_diff(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
) -> None:
    run_id = launch_same(user_client, project)
    wait_for(worker, db, run_id, timeout=120)
    assert user_client.delete(f"/api/v1/runs/{run_id}").status_code == 204

    assert user_client.get(f"/api/v1/runs/{run_id}/diff").status_code == 404
    assert json.loads(user_client.get(f"/api/v1/runs/{run_id}").text)["status"] == "purged"
