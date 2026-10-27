"""Fase 9: subidas (tipos, contenido real, límites, IDOR, cuota) y carga bulk con util_bbdd real sobre SQLite.

Vista previa (validación, mapeo, filas afectadas, SQL generado sin tocar el destino) y carga insert/update/delete con
las reglas de ADR-010 (permiso + owner, vista previa reciente, mismo fichero y conexión, confirmaciones, una escritura
por destino, sin relanzar ni cancelar en curso).
"""

from __future__ import annotations

import io
import sqlite3
import zipfile
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import AuditEntry, Run, Upload, User, utcnow
from app.jobs.worker import Worker
from app.workspace.layout import run_dir
from tests.api.test_projects import login_as, new_project
from tests.api.test_runs import wait_for, worker  # noqa: F401  (fixture)

TARGET = """
CREATE TABLE clientes (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, email TEXT);
INSERT INTO clientes VALUES (1, 'ana', 'a@x'), (2, 'luis', NULL);
"""
INSERT_CSV = "ID;Nombre;Email;extra\n3;eva;e@x;z\n4;;x;z\n5;o'brien;;z\n"


def _xlsx(rows: list[list[Any]], *, macros: bool = False) -> bytes:
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.title = "Datos"
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    if not macros:
        return buffer.getvalue()
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as src, zipfile.ZipFile(out, "w") as dst:
        for item in src.infolist():
            dst.writestr(item, src.read(item))
        dst.writestr("xl/vbaProject.bin", b"macro")
    return out.getvalue()


def _rows(settings: Settings) -> list[tuple[Any, ...]]:
    con = sqlite3.connect(settings.files_dir / "destino.db")
    try:
        return list(con.execute("SELECT * FROM clientes ORDER BY id"))
    finally:
        con.close()


@pytest.fixture
def project(user_client: TestClient, settings: Settings) -> dict[str, object]:
    con = sqlite3.connect(settings.files_dir / "destino.db")
    con.executescript(TARGET)
    con.close()
    body = new_project(user_client)
    for alias, read_only in (("destino", False), ("lectura", True)):
        connection_id = user_client.post(
            "/api/v1/connections",
            json={"name": alias, "db_type": "sqlite", "params": {"database": "destino.db"}, "read_only": read_only},
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


def upload(client: TestClient, project_id: object, name: str, content: bytes | str) -> Any:
    data = content.encode("utf-8") if isinstance(content, str) else content
    return client.post(f"/api/v1/projects/{project_id}/uploads", files={"file": (name, data)})


def preview(
    client: TestClient, project: dict[str, object], worker: Worker, db: Session, upload_id: str,  # noqa: F811
    **params: object,
) -> Run:  # fmt: skip
    body = {"upload": upload_id, "target_connection": "destino", "table": "clientes", "operation": "insert", **params}
    response = client.post(f"/api/v1/projects/{project['id']}/runs", json={"operation": "bulk_preview", "params": body})
    assert response.status_code == 202, response.text
    return wait_for(worker, db, response.json()["id"], timeout=120)


def apply(client: TestClient, project: dict[str, object], preview_id: str, **extra: object) -> Any:
    params = {"preview_run": preview_id, "confirm": "destino", **extra}
    return client.post(f"/api/v1/projects/{project['id']}/runs", json={"operation": "bulk_apply", "params": params})


# --- subidas -----------------------------------------------------------------------------------------------------


def test_upload_list_info_and_delete(user_client: TestClient, project: dict[str, object], db: Session) -> None:
    created = upload(user_client, project["id"], "../../clientes nuevos.csv", INSERT_CSV)

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["filename"] == "clientes nuevos.csv" and body["kind"] == "csv" and len(body["sha256"]) == 64
    stored = db.get(Upload, body["id"])
    assert stored is not None and stored.path.endswith(f"/uploads/{body['id']}.csv") and ".." not in stored.path
    listed = user_client.get(f"/api/v1/projects/{project['id']}/uploads").json()
    assert [u["id"] for u in listed] == [body["id"]]
    info = user_client.get(f"/api/v1/projects/{project['id']}/uploads/{body['id']}/info").json()
    assert info["columns"] == ["ID", "Nombre", "Email", "extra"] and info["delimiter"] == ";"
    assert info["sample"][0] == ["3", "eva", "e@x", "z"]
    xlsx = upload(user_client, project["id"], "libro.xlsx", _xlsx([["id", "nombre"], [7, "ana"]])).json()
    assert user_client.get(f"/api/v1/projects/{project['id']}/uploads/{xlsx['id']}/info").json()["sheets"] == ["Datos"]

    assert user_client.delete(f"/api/v1/projects/{project['id']}/uploads/{body['id']}").status_code == 204
    actions = {e.action for e in db.scalars(select(AuditEntry)).all()}
    assert {"upload.create", "upload.delete"} <= actions


@pytest.mark.parametrize(
    ("name", "content", "status"),
    [
        ("datos.txt", "a,b\n1,2\n", 415),
        ("sin_extension", "a,b\n", 415),
        ("binario.csv", b"a,b\n\x00\x01\x02", 422),
        ("falso.xlsx", "esto no es un zip", 422),
        ("macros.xlsx", "MACROS", 422),
    ],
)
def test_upload_rejects_wrong_types_and_content(
    user_client: TestClient, project: dict[str, object], settings: Settings, name: str, content: Any, status: int
) -> None:
    data = _xlsx([["a"], [1]], macros=True) if content == "MACROS" else content

    response = upload(user_client, project["id"], name, data)

    assert response.status_code == status, response.text
    folder = settings.workspace_dir
    assert not [p for p in folder.rglob("*") if p.is_file() and "uploads" in p.parts]


def test_upload_limits_size_and_uncompressed_size(
    user_client: TestClient, project: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UBW_UPLOAD_MAX_MB", "1")
    monkeypatch.setenv("UBW_UPLOAD_MAX_UNCOMPRESSED_MB", "1")
    get_settings.cache_clear()
    bomb = io.BytesIO()
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", "<workbook/>")
        archive.writestr("xl/worksheets/sheet1.xml", b"0" * (3 * 1024 * 1024))

    too_big = upload(user_client, project["id"], "grande.csv", "a\n" + "1\n" * 600_000)
    zip_bomb = upload(user_client, project["id"], "bomba.xlsx", bomb.getvalue())

    assert too_big.status_code == 413
    assert zip_bomb.status_code == 422 and "descomprimido" in zip_bomb.text


def test_uploads_are_per_project_and_need_editor(
    user_client: TestClient, project: dict[str, object], make_user: Callable[..., User]
) -> None:
    body = upload(user_client, project["id"], "c.csv", INSERT_CSV).json()
    outsider = login_as(user_client, make_user, "luis")
    viewer = login_as(user_client, make_user, "vera")
    user_client.post(f"/api/v1/projects/{project['id']}/members", json={"username": "vera"})
    other = new_project(user_client, "Otro")

    assert outsider.get(f"/api/v1/projects/{project['id']}/uploads").status_code == 404
    assert user_client.get(f"/api/v1/projects/{other['id']}/uploads/{body['id']}/info").status_code == 404
    assert upload(viewer, project["id"], "v.csv", INSERT_CSV).status_code == 403
    assert viewer.delete(f"/api/v1/projects/{project['id']}/uploads/{body['id']}").status_code == 403
    # Una vista previa no puede usar un fichero de otro proyecto (IDOR).
    response = user_client.post(
        f"/api/v1/projects/{other['id']}/runs",
        json={"operation": "bulk_preview",
              "params": {"upload": body["id"], "target_connection": "destino", "table": "t", "operation": "insert"}},
    )  # fmt: skip
    assert response.status_code == 422


# --- vista previa y carga ----------------------------------------------------------------------------------------


def test_insert_preview_generates_sql_without_touching_the_target_and_apply_inserts(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
    allowed: User,
) -> None:
    upload_id = upload(user_client, project["id"], "c.csv", INSERT_CSV).json()["id"]
    run = preview(user_client, project, worker, db, upload_id, on_error="isolate")

    assert run.status == "succeeded", (run.error_code, run.error_message)
    body = user_client.get(f"/api/v1/runs/{run.id}/bulk-preview").json()
    assert body["errors"] == [] and body["rows"] == 3
    assert body["mapping"] == {"ID": "id", "Nombre": "nombre", "Email": "email"}
    assert body["ignored_columns"] == ["extra"] and body["matches"] == 0
    sql = (run_dir(settings.workspace_dir, str(run.workspace_path)) / "outputs" / body["sql_file"]).read_text()
    assert "INSERT INTO clientes" in sql and "'o''brien'" in sql
    assert _rows(settings) == [(1, "ana", "a@x"), (2, "luis", None)]  # el modo seco no escribe

    response = apply(user_client, project, run.id)
    assert response.status_code == 202, response.text
    done = wait_for(worker, db, response.json()["id"], timeout=120)

    assert done.status == "succeeded", (done.error_code, done.error_message)
    result = user_client.get(f"/api/v1/runs/{done.id}/bulk-result").json()
    assert (result["target_rows_before"], result["target_rows_after"], result["rejected"]) == (2, 4, 1)
    # G37: util_bbdd cuenta las filas enviadas (también la apartada); con rechazos no se verifica el recuento.
    assert (result["committed"], result["verified"]) == (3, None)
    assert [r[0] for r in _rows(settings)] == [1, 2, 3, 5]
    entry = db.scalars(select(AuditEntry).where(AuditEntry.target_id == done.id)).one()
    assert (entry.details or {})["bulk"]["operation"] == "insert"


def test_update_and_delete_need_the_exact_row_count(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
    allowed: User,
) -> None:
    upd = upload(user_client, project["id"], "u.csv", "id,nombre\n1,ANA\n2,LUIS\n99,nadie\n").json()["id"]
    dele = upload(user_client, project["id"], "d.csv", "id\n2\n98\n").json()["id"]
    upd_run = preview(user_client, project, worker, db, upd, operation="update")
    del_run = preview(user_client, project, worker, db, dele, operation="delete")
    assert user_client.get(f"/api/v1/runs/{upd_run.id}/bulk-preview").json()["matches"] == 2

    assert apply(user_client, project, upd_run.id).status_code == 422
    assert apply(user_client, project, upd_run.id, confirm_rows=3).status_code == 422
    ok = apply(user_client, project, upd_run.id, confirm_rows=2)
    assert ok.status_code == 202, ok.text
    assert wait_for(worker, db, ok.json()["id"], timeout=120).status == "succeeded"
    removed = apply(user_client, project, del_run.id, confirm_rows=1)
    assert removed.status_code == 202, removed.text
    assert wait_for(worker, db, removed.json()["id"], timeout=120).status == "succeeded"

    assert _rows(settings) == [(1, "ANA", "a@x")]
    # G37: las claves que no existen (99, 98) cuentan como enviadas; el recuento del destino cuadra.
    updated = user_client.get(f"/api/v1/runs/{ok.json()['id']}/bulk-result").json()
    deleted = user_client.get(f"/api/v1/runs/{removed.json()['id']}/bulk-result").json()
    assert (updated["committed"], updated["verified"]) == (3, True)
    assert (deleted["committed"], deleted["matches"], deleted["verified"]) == (2, 1, True)


def test_apply_aborts_if_the_affected_rows_changed(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
    allowed: User,
) -> None:
    """Se confirmó borrar 2 filas; si al aplicar coinciden otras, no se escribe nada."""
    dele = upload(user_client, project["id"], "d.csv", "id\n1\n2\n").json()["id"]
    del_run = preview(user_client, project, worker, db, dele, operation="delete")
    con = sqlite3.connect(settings.files_dir / "destino.db")
    con.execute("DELETE FROM clientes WHERE id = 2")
    con.commit()
    con.close()

    response = apply(user_client, project, del_run.id, confirm_rows=2)
    assert response.status_code == 202, response.text
    done = wait_for(worker, db, response.json()["id"], timeout=120)
    assert done.status == "failed"
    assert done.error_code == "preview_changed"
    assert "Ahora coinciden 1 filas" in (done.error_message or "")
    assert _rows(settings) == [(1, "ana", "a@x")]


def test_validation_errors_block_the_apply(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    allowed: User,
) -> None:
    upload_id = upload(user_client, project["id"], "c.csv", "id\n3\n").json()["id"]
    run = preview(user_client, project, worker, db, upload_id)
    unknown = preview(user_client, project, worker, db, upload_id, mapping={"id": "no_existe"})
    no_table = preview(user_client, project, worker, db, upload_id, table="no_existe")

    body = user_client.get(f"/api/v1/runs/{run.id}/bulk-preview").json()
    assert body["errors"] == ["Faltan columnas obligatorias: nombre."] and body["sql_file"] is None
    assert "no_existe" in user_client.get(f"/api/v1/runs/{unknown.id}/bulk-preview").json()["errors"][0]
    assert (no_table.status, no_table.error_code) == ("failed", "invalid_params")
    assert apply(user_client, project, run.id).status_code == 409


def test_apply_rules(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
    user: User,
    make_user: Callable[..., User],
) -> None:
    upload_id = upload(user_client, project["id"], "c.csv", INSERT_CSV).json()["id"]
    run = preview(user_client, project, worker, db, upload_id, on_error="isolate")
    read_only = preview(user_client, project, worker, db, upload_id, target_connection="lectura", on_error="isolate")

    assert apply(user_client, project, run.id).status_code == 403  # sin permiso
    db.execute(update(User).where(User.id == user.id).values(can_write_data=True))
    db.commit()
    assert apply(user_client, project, read_only.id, confirm="lectura").status_code == 422
    assert apply(user_client, project, run.id, confirm="Destino").status_code == 422
    db.execute(update(Run).where(Run.id == run.id).values(finished_at=utcnow() - timedelta(minutes=61)))
    db.commit()
    assert "60 minutos" in apply(user_client, project, run.id).text
    db.execute(update(Run).where(Run.id == run.id).values(finished_at=utcnow()))
    db.commit()

    eva = login_as(user_client, make_user, "eva")
    user_client.post(f"/api/v1/projects/{project['id']}/members", json={"username": "eva", "role": "editor"})
    db.execute(update(User).where(User.username == "eva").values(can_write_data=True))
    db.commit()
    assert apply(eva, project, run.id).status_code == 403

    first = apply(user_client, project, run.id)
    assert first.status_code == 202, first.text
    assert apply(user_client, project, run.id).status_code == 409  # una escritura por destino
    assert user_client.delete(f"/api/v1/projects/{project['id']}/uploads/{upload_id}").status_code == 409  # en uso
    assert user_client.post(f"/api/v1/runs/{first.json()['id']}/relaunch").status_code == 409
    db.execute(update(Run).where(Run.id == first.json()["id"]).values(status="running"))
    db.commit()
    assert user_client.post(f"/api/v1/runs/{first.json()['id']}/cancel").status_code == 409


def test_changed_file_or_connection_invalidates_the_preview(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
    allowed: User,
) -> None:
    upload_id = upload(user_client, project["id"], "c.csv", INSERT_CSV).json()["id"]
    run = preview(user_client, project, worker, db, upload_id, on_error="isolate")
    db.execute(update(Upload).where(Upload.id == upload_id).values(sha256="0" * 64))
    db.commit()

    response = apply(user_client, project, run.id)

    assert response.status_code == 422 and "fichero" in response.text
    assert _rows(settings) == [(1, "ana", "a@x"), (2, "luis", None)]


def test_parallel_plan_needs_accepting_non_atomic(
    user_client: TestClient,
    project: dict[str, object],
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
    allowed: User,
) -> None:
    """Con SQLite el plan siempre es en serie: se simula un plan de 4 hilos no atómico en la vista previa guardada."""
    import json

    upload_id = upload(user_client, project["id"], "c.csv", INSERT_CSV).json()["id"]
    run = preview(user_client, project, worker, db, upload_id, on_error="isolate", parallel=True)
    path = run_dir(settings.workspace_dir, str(run.workspace_path)) / "outputs" / "bulk" / "preview.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["parallel"]["workers"] == 1 and data["parallel"]["reasons"]
    assert data["parallel"]["atomic"] is True  # G36: ParallelPlan.atomic de util_bbdd
    data["parallel"].update(workers=4, atomic=False)
    path.write_text(json.dumps(data), encoding="utf-8")

    refused = apply(user_client, project, run.id)
    accepted = apply(user_client, project, run.id, accept_non_atomic=True)

    assert refused.status_code == 422 and "atómica" in refused.text
    assert accepted.status_code == 202, accepted.text
