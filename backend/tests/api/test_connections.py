"""Motores, conexiones y allowlist por HTTP: permisos (401/403/404), secretos, prueba real con SQLite y errores."""

from __future__ import annotations

import io
import logging
import sqlite3
import threading
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cli import main as cli_main
from app.core.config import Settings
from app.db.models import AuditEntry, Connection, User
from app.domain.connections import service
from app.integrations.util_bbdd import probe
from tests.conftest import USER_PASSWORD, do_login

SECRET = "pg-secreta-123"
PG = {
    "name": "Ventas",
    "db_type": "postgresql",
    "params": {"host": "db.corp.local", "user": "lector", "database": "ventas", "port": 5432},
    "password": SECRET,
}


@pytest.fixture
def sqlite_file(settings: Settings) -> Path:
    path = settings.files_dir / "demo.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    con.close()
    return path


def _second_user(client: TestClient, make_user: Callable[..., User], username: str = "luis") -> TestClient:
    make_user(username, USER_PASSWORD, "user")
    other = TestClient(client.app, base_url="https://testserver")
    do_login(other, username, USER_PASSWORD)
    return other


# --- engines -----------------------------------------------------------------------------------------------------


def test_engines_require_session(client: TestClient) -> None:
    assert client.get("/api/v1/engines").status_code == 401


def test_engine_catalog_and_detail(user_client: TestClient) -> None:
    engines = user_client.get("/api/v1/engines").json()
    detail = user_client.get("/api/v1/engines/PostgreSQL").json()

    assert len(engines) == 7
    pg = next(e for e in engines if e["db_type"] == "postgresql")
    assert pg["capabilities"] == {
        "async_supported": True,
        "migrate_source": True,
        "migrate_target": True,
        "readiness": True,
    }
    assert detail["default_port"] == 5432
    params = {p["name"]: p for p in detail["params"]}
    assert params["password"]["kind"] == "secret"
    assert params["host"] == {**params["host"], "required": True, "kind": "host"}
    assert params["sslmode"]["options"][0] == "disable"
    assert user_client.get("/api/v1/engines/db2").status_code == 404


# --- CRUD y permisos ---------------------------------------------------------------------------------------------


def test_create_list_get_without_secret(user_client: TestClient, db: Session, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    created = user_client.post("/api/v1/connections", json=PG)

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["has_password"] is True
    assert body["read_only"] is True
    assert body["visibility"] == "private"
    assert body["editable"] is True
    assert SECRET not in created.text
    assert SECRET not in user_client.get(f"/api/v1/connections/{body['id']}").text
    assert [c["name"] for c in user_client.get("/api/v1/connections").json()["items"]] == ["Ventas"]
    row = db.scalars(select(Connection)).one()
    assert row.secret_enc is not None and SECRET not in row.secret_enc
    assert SECRET not in str(row.params)
    assert SECRET not in caplog.text
    assert SECRET not in " ".join(str(e.details) for e in db.scalars(select(AuditEntry)).all())


@pytest.mark.parametrize(
    ("change", "status"),
    [
        ({"db_type": "db2"}, 404),
        ({"params": {**PG["params"], "nope": 1}}, 422),
        ({"params": {"host": "x"}}, 422),
        ({"params": {**PG["params"], "password": "x"}}, 422),
        ({"name": ""}, 422),
        ({"visibility": "shared"}, 403),
    ],
)
def test_create_rejects(user_client: TestClient, change: dict[str, object], status: int) -> None:
    response = user_client.post("/api/v1/connections", json={**PG, **change})

    assert response.status_code == status, response.text


def test_missing_required_param_points_to_util_bbdd_message(user_client: TestClient) -> None:
    response = user_client.post("/api/v1/connections", json={**PG, "params": {"host": "db", "database": "x"}})

    assert response.status_code == 422
    assert "user" in response.json()["detail"]


def test_duplicate_name_conflicts(user_client: TestClient) -> None:
    user_client.post("/api/v1/connections", json=PG)

    assert user_client.post("/api/v1/connections", json={**PG, "name": "ventas"}).status_code == 409


def test_private_connection_of_other_user_is_404(user_client: TestClient, make_user: Callable[..., User]) -> None:
    connection_id = user_client.post("/api/v1/connections", json=PG).json()["id"]
    other = _second_user(user_client, make_user)

    assert other.get(f"/api/v1/connections/{connection_id}").status_code == 404
    assert other.patch(f"/api/v1/connections/{connection_id}", json={"name": "x"}).status_code == 404
    assert other.delete(f"/api/v1/connections/{connection_id}").status_code == 404
    assert other.post(f"/api/v1/connections/{connection_id}/test").status_code == 404
    assert other.get(f"/api/v1/connections/{connection_id}/readiness").status_code == 404
    assert other.get("/api/v1/connections").json()["total"] == 0


def test_shared_connection_visible_but_read_only_for_users(
    admin_client: TestClient, make_user: Callable[..., User]
) -> None:
    shared = admin_client.post("/api/v1/connections", json={**PG, "visibility": "shared"}).json()
    ana = _second_user(admin_client, make_user, "ana")

    seen = ana.get(f"/api/v1/connections/{shared['id']}")
    assert seen.status_code == 200
    assert seen.json()["editable"] is False
    assert SECRET not in seen.text
    assert ana.patch(f"/api/v1/connections/{shared['id']}", json={"name": "mía"}).status_code == 403
    assert ana.delete(f"/api/v1/connections/{shared['id']}").status_code == 403
    own = ana.post("/api/v1/connections", json=PG).json()
    assert ana.patch(f"/api/v1/connections/{own['id']}", json={"visibility": "shared"}).status_code == 403


def test_admin_cannot_see_private_connections_of_others(
    user_client: TestClient, make_user: Callable[..., User]
) -> None:
    connection_id = user_client.post("/api/v1/connections", json=PG).json()["id"]
    make_user("jefa", USER_PASSWORD, "admin")
    admin = TestClient(user_client.app, base_url="https://testserver")
    do_login(admin, "jefa", USER_PASSWORD)

    assert admin.get(f"/api/v1/connections/{connection_id}").status_code == 404


def test_update_keeps_password_when_omitted_and_resets_last_test(user_client: TestClient, db: Session) -> None:
    connection_id = user_client.post("/api/v1/connections", json=PG).json()["id"]
    row = db.get(Connection, connection_id)
    assert row is not None
    before = row.secret_enc
    row.last_test_ok = True
    db.commit()

    response = user_client.patch(
        f"/api/v1/connections/{connection_id}", json={"params": {**PG["params"], "port": 5433}, "read_only": False}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["params"]["port"], body["has_password"], body["read_only"], body["last_test_ok"]) == (
        5433,
        True,
        False,
        None,
    )
    db.expire_all()
    assert db.get(Connection, connection_id).secret_enc == before  # type: ignore[union-attr]


def test_delete_connection(user_client: TestClient) -> None:
    connection_id = user_client.post("/api/v1/connections", json=PG).json()["id"]

    assert user_client.delete(f"/api/v1/connections/{connection_id}").status_code == 204
    assert user_client.get(f"/api/v1/connections/{connection_id}").status_code == 404


def test_connections_require_session(client: TestClient) -> None:
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]

    assert client.get("/api/v1/connections").status_code == 401
    assert client.post("/api/v1/connections", json=PG, headers={"X-CSRF-Token": csrf}).status_code == 401


# --- prueba y readiness ------------------------------------------------------------------------------------------


def test_real_sqlite_test_and_readiness_in_subprocess(user_client: TestClient, sqlite_file: Path) -> None:
    connection_id = user_client.post(
        "/api/v1/connections", json={"name": "Demo", "db_type": "sqlite", "params": {"database": sqlite_file.name}}
    ).json()["id"]

    tested = user_client.post(f"/api/v1/connections/{connection_id}/test").json()
    report = user_client.get(f"/api/v1/connections/{connection_id}/readiness").json()

    assert tested["ok"] is True, tested
    assert tested["server_version"]
    assert tested["error"] is None
    assert report["supported"] is True and report["dynamic"] is True
    assert {f["param"] for f in report["findings"]} >= {"journal_mode"}
    assert user_client.get(f"/api/v1/connections/{connection_id}").json()["last_test_ok"] is True


def test_missing_sqlite_file_fails_with_sanitized_error(user_client: TestClient, settings: Settings) -> None:
    connection_id = user_client.post(
        "/api/v1/connections", json={"name": "Nada", "db_type": "sqlite", "params": {"database": "no/existe.db"}}
    ).json()["id"]

    tested = user_client.post(f"/api/v1/connections/{connection_id}/test").json()

    assert tested["ok"] is False
    assert tested["error"]["code"] == "connection_failed"
    assert str(settings.files_dir) not in str(tested)


def test_target_not_in_allowlist_is_not_contacted(user_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_: object, **__: object) -> None:
        raise AssertionError("no debe conectar")

    monkeypatch.setattr(probe, "check_connection", fail)
    connection_id = user_client.post(
        "/api/v1/connections", json={**PG, "params": {**PG["params"], "host": "10.1.2.3"}}
    ).json()["id"]

    tested = user_client.post(f"/api/v1/connections/{connection_id}/test").json()

    assert tested["error"]["code"] == "not_allowed"
    assert "lista de destinos permitidos" in tested["error"]["message"]


def test_allowlisted_target_is_probed_with_decrypted_password(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch, db: Session
) -> None:
    seen: dict[str, object] = {}

    def fake(db_type: str, conn_params: dict[str, object], *, timeout: float) -> probe.ConnectionCheck:
        seen.update(conn_params, db_type=db_type, timeout=timeout)
        return probe.ConnectionCheck(
            ok=False,
            duration_ms=5,
            server_version=None,
            error=probe.ProbeError("connection_failed", "OperationalError"),
        )

    monkeypatch.setattr(probe, "check_connection", fake)
    assert admin_client.post("/api/v1/admin/allowlist", json={"pattern": "10.0.0.0/8"}).status_code == 201
    connection_id = admin_client.post(
        "/api/v1/connections", json={**PG, "params": {**PG["params"], "host": "10.1.2.3"}}
    ).json()["id"]

    tested = admin_client.post(f"/api/v1/connections/{connection_id}/test").json()

    assert tested["error"] == {"code": "connection_failed", "message": service.ERROR_MESSAGES["connection_failed"]}
    assert seen["password"] == SECRET
    assert seen["connect_timeout"] == 10
    assert seen["db_type"] == "postgresql"
    assert SECRET not in str(tested)
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "connection.test")).one()
    assert (entry.outcome, entry.details) == ("failure", {"error": "connection_failed"})


def test_too_many_concurrent_probes(
    user_client: TestClient, sqlite_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "_PROBES", threading.BoundedSemaphore(1))
    service._PROBES.acquire()
    connection_id = user_client.post(
        "/api/v1/connections", json={"name": "Demo", "db_type": "sqlite", "params": {"database": sqlite_file.name}}
    ).json()["id"]

    assert user_client.post(f"/api/v1/connections/{connection_id}/test").status_code == 429


def test_shared_connection_can_be_tested_by_users(
    admin_client: TestClient, make_user: Callable[..., User], sqlite_file: Path
) -> None:
    shared = admin_client.post(
        "/api/v1/connections",
        json={"name": "Común", "db_type": "sqlite", "params": {"database": sqlite_file.name}, "visibility": "shared"},
    ).json()
    ana = _second_user(admin_client, make_user, "ana")

    assert ana.post(f"/api/v1/connections/{shared['id']}/test").json()["ok"] is True


# --- allowlist ---------------------------------------------------------------------------------------------------


def test_allowlist_is_admin_only(user_client: TestClient) -> None:
    assert user_client.get("/api/v1/admin/allowlist").status_code == 403
    assert user_client.post("/api/v1/admin/allowlist", json={"pattern": "*"}).status_code == 403


def test_allowlist_crud(admin_client: TestClient) -> None:
    created = admin_client.post("/api/v1/admin/allowlist", json={"pattern": "*.Corp.Local", "description": "LAN"})

    assert created.status_code == 201
    assert created.json()["pattern"] == "*.corp.local"
    assert admin_client.post("/api/v1/admin/allowlist", json={"pattern": "*.corp.local"}).status_code == 409
    assert admin_client.post("/api/v1/admin/allowlist", json={"pattern": "http://x"}).status_code == 422
    assert [e["pattern"] for e in admin_client.get("/api/v1/admin/allowlist").json()] == ["*.corp.local"]
    assert admin_client.delete(f"/api/v1/admin/allowlist/{created.json()['id']}").status_code == 204
    assert admin_client.delete(f"/api/v1/admin/allowlist/{created.json()['id']}").status_code == 404


# --- CLI ---------------------------------------------------------------------------------------------------------


def test_rotate_secrets_cli(
    user_client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    from cryptography.fernet import Fernet

    from app.core.config import get_settings
    from app.domain.connections.crypto import SecretBox

    user_client.post("/api/v1/connections", json=PG)
    new_key = Fernet.generate_key().decode()
    old_key = settings.fernet_keys.get_secret_value()  # type: ignore[union-attr]
    monkeypatch.setenv("UBW_FERNET_KEYS", f"{new_key},{old_key}")
    get_settings.cache_clear()
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    assert cli_main(["rotate-secrets"]) == 0

    db.expire_all()
    token = db.scalars(select(Connection.secret_enc)).one()
    assert token is not None
    assert SecretBox([new_key]).decrypt(token) == {"password": SECRET}


def test_unresolvable_host_is_connection_failed_not_allowlist(
    user_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.domain.connections import allowlist

    def no_dns(host: str) -> list[object]:
        raise OSError(f"no resuelve {host}")

    monkeypatch.setattr(allowlist, "resolve", no_dns)
    connection_id = user_client.post("/api/v1/connections", json=PG).json()["id"]

    tested = user_client.post(f"/api/v1/connections/{connection_id}/test").json()

    assert tested["error"]["code"] == "connection_failed"
