"""Fase 8: volcado de datos con util_bbdd real entre dos SQLite (apto para el CI) y reglas de ADR-009.

Vista previa (orden por FK, ciclos, filas, avisos), volcado añadiendo y vaciando, rechazos aislados, errores sin
datos de filas, ``preview_changed`` y las reglas al encolar (permiso + owner, caducidad, destino ``read_only``,
confirmaciones, sin dos volcados a la vez, sin relanzar ni cancelar en curso).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, Run, User, utcnow
from app.jobs.worker import Worker
from app.workspace.layout import run_dir
from tests.api.test_projects import login_as, new_project
from tests.api.test_runs import wait_for, worker  # noqa: F401  (fixture)

SCHEMA = """
CREATE TABLE clientes (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL);
CREATE TABLE pedidos (id INTEGER PRIMARY KEY, cliente_id INTEGER REFERENCES clientes(id), total NUMERIC);
CREATE TABLE lineas (id INTEGER PRIMARY KEY, pedido_id INTEGER REFERENCES pedidos(id));
CREATE TABLE a (id INTEGER PRIMARY KEY, b_id INTEGER REFERENCES b(id));
CREATE TABLE b (id INTEGER PRIMARY KEY, a_id INTEGER REFERENCES a(id));
CREATE TABLE sueltas (id INTEGER PRIMARY KEY, v TEXT);
"""
# El origen admite un nombre nulo (el destino no): esa fila es rechazable. «secreto» no debe salir en ningún error.
DATA = """
INSERT INTO clientes VALUES (1, 'secreto'), (2, NULL);
INSERT INTO pedidos VALUES (10, 1, 5), (11, 1, 7);
INSERT INTO lineas VALUES (100, 10);
INSERT INTO a VALUES (1, NULL); INSERT INTO b VALUES (1, 1);
INSERT INTO sueltas VALUES (1, 'x');
"""
TARGET = SCHEMA.replace("CREATE TABLE sueltas (id INTEGER PRIMARY KEY, v TEXT);", "")


def _db(settings: Settings, name: str, script: str) -> None:
    path = settings.files_dir / name
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    con.executescript(script)
    con.close()


def _rows(settings: Settings, table: str) -> list[tuple[Any, ...]]:
    con = sqlite3.connect(settings.files_dir / "destino.db")
    try:
        return list(con.execute(f"SELECT * FROM {table} ORDER BY id"))  # noqa: S608 (nombre fijo del test)
    finally:
        con.close()


@pytest.fixture
def project(user_client: TestClient, settings: Settings) -> dict[str, object]:
    _db(settings, "origen.db", SCHEMA.replace("nombre TEXT NOT NULL", "nombre TEXT") + DATA)
    _db(settings, "destino.db", TARGET + "INSERT INTO pedidos VALUES (99, NULL, 1);")
    body = new_project(user_client)
    for alias, database, read_only in [
        ("origen", "origen.db", True), ("destino", "destino.db", False), ("lectura", "destino.db", True),
    ]:  # fmt: skip
        connection_id = user_client.post(
            "/api/v1/connections",
            json={"name": alias, "db_type": "sqlite", "params": {"database": database}, "read_only": read_only},
        ).json()["id"]
        response = user_client.post(
            f"/api/v1/projects/{body['id']}/connections", json={"connection_id": connection_id, "alias": alias}
        )
        assert response.status_code == 201, response.text
    return body


@pytest.fixture
def allowed(db: Session, user: User) -> User:
    db.execute(update(User).where(User.id == user.id).values(can_write_data=True))
    db.commit()
    return user


def launch(client: TestClient, project_id: object, operation: str, **params: object) -> Any:
    return client.post(f"/api/v1/projects/{project_id}/runs", json={"operation": operation, "params": params})


def preview(
    client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    **params: object,
) -> str:
    body = {"source_connection": "origen", "target_connection": "destino", **params}
    response = launch(client, project["id"], "dump_preview", **body)
    assert response.status_code == 202, response.text
    run = wait_for(worker, db, response.json()["id"], timeout=120)
    assert run.status == "succeeded", (run.error_code, run.error_message)
    return run.id


def apply(
    client: TestClient, project: dict[str, object], preview_id: str, confirm: str = "destino", **extra: object
) -> Any:
    return launch(client, project["id"], "dump_apply", preview_run=preview_id, confirm=confirm, **extra)


# --- vista previa ------------------------------------------------------------------------------------------------


def test_preview_shows_order_cycles_rows_and_warnings(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
) -> None:
    run_id = preview(user_client, project, worker, db)

    body = user_client.get(f"/api/v1/runs/{run_id}/dump-preview").json()

    assert body["load_order"] == ["clientes", "sueltas", "pedidos", "lineas", "a", "b"]
    assert body["cycles"] == [["a", "b"]]
    tables = {t["table"]: t for t in body["tables"]}
    assert tables["sueltas"]["target_table"] is None
    assert (tables["pedidos"]["source_rows"], tables["pedidos"]["target_rows"]) == (2, 1)
    assert tables["a"]["in_cycle"] is True and tables["clientes"]["in_cycle"] is False
    assert body["truncate_target"] is False and body["constraints_managed"] is False


def test_preview_rejects_unknown_tables_and_accepts_any_case(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
) -> None:
    unknown = launch(
        user_client, project["id"], "dump_preview", source_connection="origen", target_connection="destino",
        tables="clientes, no_existe",
    ).json()["id"]  # fmt: skip
    run = wait_for(worker, db, unknown, timeout=120)
    ok = preview(user_client, project, worker, db, tables="LINEAS, pedidos ,Clientes")

    assert (run.status, run.error_code) == ("failed", "invalid_params")
    assert "no_existe" in str(run.error_message)
    assert user_client.get(f"/api/v1/runs/{ok}/dump-preview").json()["load_order"] == ["clientes", "pedidos", "lineas"]


# --- volcado -----------------------------------------------------------------------------------------------------


def test_dump_appends_isolates_rejects_and_reports(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
    allowed: User,
) -> None:
    preview_id = preview(user_client, project, worker, db, on_error="isolate")
    response = apply(user_client, project, preview_id)
    assert response.status_code == 202, response.text
    run = wait_for(worker, db, response.json()["id"], timeout=180)

    assert run.status == "succeeded", (run.error_code, run.error_message)
    assert "1 filas apartadas" in str(run.progress_message)
    result = user_client.get(f"/api/v1/runs/{run.id}/dump-result").json()
    # La vista previa calcula el mismo orden que util_bbdd (G29: sin API pública de vista previa).
    assert result["load_order"] == user_client.get(f"/api/v1/runs/{preview_id}/dump-preview").json()["load_order"]
    tables = {t["table"]: t for t in result["tables"]}
    assert tables["clientes"]["rows_rejected"] == 1
    assert tables["sueltas"]["status"] == "missing_target"
    assert result["report"] is True
    assert _rows(settings, "pedidos") == [(10, 1, 5), (11, 1, 7), (99, None, 1)]  # se añadió: sigue la 99
    paths = {a["path"] for a in user_client.get(f"/api/v1/runs/{run.id}").json()["artifacts"]}
    assert {"outputs/excel/volcado.xlsx", "outputs/rejects/rechazos.csv", "outputs/audit/volcado.jsonl",
            "outputs/dump/result.json"} <= paths  # fmt: skip
    entry = db.scalars(select(AuditEntry).where(AuditEntry.target_id == run.id)).one()
    details = entry.details or {}
    assert details["operation"] == "dump_apply"
    assert details["dump"] == {
        "preview_run": preview_id, "source_connection": "origen", "target_connection": "destino", "tables": None,
        "truncate_target": False, "on_error": "isolate",
    }  # fmt: skip


def test_dump_error_is_partial_and_never_shows_row_data(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
    allowed: User,
) -> None:
    preview_id = preview(user_client, project, worker, db)
    run = wait_for(worker, db, apply(user_client, project, preview_id).json()["id"], timeout=180)

    assert (run.status, run.error_code) == ("failed", "dump_partial")
    assert "clientes" in str(run.error_message)
    result = user_client.get(f"/api/v1/runs/{run.id}/dump-result").json()
    error = {t["table"]: t for t in result["tables"]}["clientes"]["error"]
    assert error and "NOT NULL" in error
    directory = run_dir(settings.workspace_dir, str(run.workspace_path))
    for name in ("outputs/dump/result.json", "run.json"):
        text = (directory / name).read_text(encoding="utf-8")
        assert "secreto" not in text and "[parameters" not in text, name


def test_truncate_needs_the_word_and_empties_the_target(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
    allowed: User,
) -> None:
    preview_id = preview(user_client, project, worker, db, truncate_target=True, on_error="isolate")

    missing = apply(user_client, project, preview_id)
    wrong = apply(user_client, project, preview_id, confirm_truncate="vaciar")
    ok = apply(user_client, project, preview_id, confirm_truncate="VACIAR")

    assert missing.status_code == wrong.status_code == 422 and "VACIAR" in wrong.text
    assert ok.status_code == 202, ok.text
    run = wait_for(worker, db, ok.json()["id"], timeout=180)
    assert run.status == "succeeded", (run.error_code, run.error_message)
    assert _rows(settings, "pedidos") == [(10, 1, 5), (11, 1, 7)]  # la 99 se borró al vaciar


def test_structure_change_after_preview_aborts_before_writing(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
    allowed: User,
) -> None:
    preview_id = preview(user_client, project, worker, db, on_error="isolate")
    con = sqlite3.connect(settings.files_dir / "destino.db")
    con.execute("ALTER TABLE pedidos DROP COLUMN total")
    con.close()

    run = wait_for(worker, db, apply(user_client, project, preview_id).json()["id"], timeout=180)

    assert (run.status, run.error_code) == ("failed", "preview_changed")
    assert _rows(settings, "pedidos") == [(99, None)]


# --- reglas al encolar -------------------------------------------------------------------------------------------


def test_apply_rules(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    user: User,
    make_user: Callable[..., User],
) -> None:
    preview_id = preview(user_client, project, worker, db)
    read_only = preview(user_client, project, worker, db, target_connection="lectura")

    assert apply(user_client, project, preview_id).status_code == 403  # sin permiso
    db.execute(update(User).where(User.id == user.id).values(can_write_data=True))
    db.commit()
    assert apply(user_client, project, read_only, confirm="lectura").status_code == 422
    assert apply(user_client, project, preview_id, confirm="Destino").status_code == 422
    db.execute(update(Run).where(Run.id == preview_id).values(finished_at=utcnow() - timedelta(minutes=61)))
    db.commit()
    stale = apply(user_client, project, preview_id)
    assert stale.status_code == 422 and "60 minutos" in stale.text
    db.execute(update(Run).where(Run.id == preview_id).values(finished_at=utcnow()))
    db.commit()

    eva = login_as(user_client, make_user, "eva")
    user_client.post(f"/api/v1/projects/{project['id']}/members", json={"username": "eva", "role": "editor"})
    eva_user = db.scalar(select(User).where(User.username == "eva"))
    assert eva_user is not None
    db.execute(update(User).where(User.id == eva_user.id).values(can_write_data=True))
    db.commit()
    not_owner = apply(eva, project, preview_id)
    assert not_owner.status_code == 403 and "propietario" in not_owner.text

    first = apply(user_client, project, preview_id)
    assert first.status_code == 202, first.text
    assert apply(user_client, project, preview_id).status_code == 409  # otro volcado sobre el mismo destino
    assert user_client.post(f"/api/v1/runs/{first.json()['id']}/relaunch").status_code == 409
    db.execute(update(Run).where(Run.id == first.json()["id"]).values(status="running"))
    db.commit()
    assert user_client.post(f"/api/v1/runs/{first.json()['id']}/cancel").status_code == 409


def test_catalog_and_permission(
    user_client: TestClient, user: User, make_user: Callable[..., User], db: Session
) -> None:
    operations = {o["name"]: o for o in user_client.get("/api/v1/operations").json()}
    admin = login_as(user_client, make_user, "jefa", role="admin")

    assert operations["dump_preview"]["form"] is True and operations["dump_apply"]["form"] is False
    assert user_client.get("/api/v1/auth/me").json()["can_write_data"] is False
    assert admin.patch(f"/api/v1/users/{user.id}", json={"can_write_data": True}).json()["can_write_data"] is True
    assert user_client.get("/api/v1/auth/me").json()["can_write_data"] is True


@pytest.mark.xfail(strict=True, reason="G33 resuelto en util_bbdd 4.4.0: el volcado ya no falla (W-V4 retira el aviso)")
def test_sqlite_dates_are_warned_and_fail_as_util_bbdd_does(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
    allowed: User,
) -> None:
    """G33: SQLite guarda DATE como texto y util_bbdd no lo convierte al insertar en un destino SQLite."""
    for name in ("origen.db", "destino.db"):
        con = sqlite3.connect(settings.files_dir / name)
        con.execute("CREATE TABLE altas (id INTEGER PRIMARY KEY, alta DATE)")
        if name == "origen.db":
            con.execute("INSERT INTO altas VALUES (1, '2026-01-01')")
        con.commit()
        con.close()
    preview_id = preview(user_client, project, worker, db, tables="altas")

    body = user_client.get(f"/api/v1/runs/{preview_id}/dump-preview").json()
    run = wait_for(worker, db, apply(user_client, project, preview_id).json()["id"], timeout=180)

    assert "sqlite_dates" in body["warnings"]
    assert body["tables"][0]["date_columns"] == ["alta"]
    assert (run.status, run.error_code) == ("failed", "dump_partial")
    error = user_client.get(f"/api/v1/runs/{run.id}/dump-result").json()["tables"][0]["error"]
    assert "Date type only accepts Python date objects" in error


# --- auditoría de la Fase 8 --------------------------------------------------------------------------------------


def _repoint(client: TestClient, project: dict[str, object], settings: Settings, alias: str = "destino") -> None:
    """Quita ``alias`` y lo asocia a otra conexión del mismo motor y con las mismas tablas (misma huella)."""
    _db(settings, "otro_destino.db", TARGET)
    connection_id = client.post(
        "/api/v1/connections",
        json={"name": "otra", "db_type": "sqlite", "params": {"database": "otro_destino.db"}, "read_only": False},
    ).json()["id"]
    assert client.delete(f"/api/v1/projects/{project['id']}/connections/{alias}").status_code == 204
    response = client.post(
        f"/api/v1/projects/{project['id']}/connections", json={"connection_id": connection_id, "alias": alias}
    )
    assert response.status_code == 201, response.text


def test_repointed_alias_is_rejected_on_enqueue_and_in_the_worker(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
    allowed: User,
) -> None:
    preview_id = preview(user_client, project, worker, db, on_error="isolate")
    queued = apply(user_client, project, preview_id)  # encolado antes del cambio
    assert queued.status_code == 202, queued.text

    _repoint(user_client, project, settings)
    refused = apply(user_client, project, preview_id)
    run = wait_for(worker, db, queued.json()["id"], timeout=120)

    assert refused.status_code == 422 and "ya no es la de la vista previa" in refused.text
    assert (run.status, run.error_code) == ("failed", "preview_changed")
    assert _rows(settings, "pedidos") == [(99, None, 1)]  # no se escribió nada


def test_dump_and_migration_exclude_each_other_on_the_same_target(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    allowed: User,
) -> None:
    from app.core.ulid import new_ulid

    preview_id = preview(user_client, project, worker, db)
    migration = Run(
        id=new_ulid(), project_id=int(str(project["id"])), user_id=allowed.id, operation="migrate_apply",
        params={"plan_run": new_ulid(), "target_connection": "destino", "mode": "apply"}, status="queued",
        phase="queued", created_at=utcnow(), workspace_path=None,
    )  # fmt: skip
    db.add(migration)
    db.commit()

    response = apply(user_client, project, preview_id)

    assert response.status_code == 409 and "migración" in response.text


def test_worker_rechecks_permission_owner_and_read_only(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
    allowed: User,
) -> None:
    from app.db.models import Connection, ProjectConnection
    from app.domain.runs.operations import DumpApplyParams
    from app.jobs.context import JobContext, JobError
    from app.jobs.operations.dump import _recheck

    preview_id = preview(user_client, project, worker, db)
    run_id = apply(user_client, project, preview_id).json()["id"]
    run = db.get(Run, run_id)
    assert run is not None
    ctx = JobContext(
        run_id=run_id, project_id=int(str(project["id"])), operation="dump_apply", params=dict(run.params),
        run_dir=settings.workspace_dir, settings=settings,
    )  # fmt: skip

    def code() -> str:
        with pytest.raises(JobError) as info:
            _recheck(ctx, DumpApplyParams.model_validate(run.params))
        return f"{info.value.code}: {info.value.message}"

    assert _recheck(ctx, DumpApplyParams.model_validate(run.params))[1]["structure_hash"]
    link = db.scalars(select(ProjectConnection).where(ProjectConnection.alias == "destino")).one()
    connection = db.get(Connection, link.connection_id)
    assert connection is not None
    connection.read_only = True
    db.commit()
    assert code().startswith("forbidden: La conexión destino es de solo lectura")
    connection.read_only = False
    db.execute(update(User).where(User.id == allowed.id).values(can_write_data=False))
    db.commit()
    assert code().startswith("forbidden: El usuario ya no tiene permiso")
