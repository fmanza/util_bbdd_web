"""Explorador, queries nombradas y SQL libre con una BD SQLite real (subprocesos reales, sin servicios externos)."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, MetadataCache, User
from tests.api.test_projects import login_as, new_project
from tests.conftest import do_login


@pytest.fixture
def demo_db(settings: Settings) -> str:
    path = settings.files_dir / "tienda.db"
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE clientes (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL UNIQUE, alta DATE);
        CREATE TABLE pedidos (
            id INTEGER PRIMARY KEY,
            cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
            total NUMERIC(10, 2) CHECK (total >= 0)
        );
        CREATE INDEX ix_pedidos_cliente ON pedidos(cliente_id);
        CREATE VIEW v_pedidos AS SELECT p.id, c.nombre FROM pedidos p JOIN clientes c ON c.id = p.cliente_id;
        INSERT INTO clientes VALUES (1, 'ana', '2026-01-01'), (2, 'luis', NULL);
        INSERT INTO pedidos VALUES (10, 1, 9.5), (11, 1, 20), (12, 2, 3.25);
        """
    )
    con.close()
    return path.name


@pytest.fixture
def connection_id(user_client: TestClient, demo_db: str) -> int:
    body = {"name": "Tienda", "db_type": "sqlite", "params": {"database": demo_db}}
    response = user_client.post("/api/v1/connections", json=body)
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


# --- metadatos ---------------------------------------------------------------------------------------------------


def test_schemas_tree_and_cache(user_client: TestClient, connection_id: int, db: Session) -> None:
    base = f"/api/v1/connections/{connection_id}/metadata/schemas"

    schemas = user_client.get(base).json()
    tree = user_client.get(f"{base}/main").json()
    cached = user_client.get(base).json()

    assert schemas["default"] == "main"
    assert schemas["schemas"] == [{"name": "main", "system": False, "cached": False}]
    assert [t["name"] for t in tree["tables"]] == ["clientes", "pedidos"]
    assert {t["name"]: t["columns"] for t in tree["tables"]} == {"clientes": 3, "pedidos": 3}
    assert [v["name"] for v in tree["views"]] == ["v_pedidos"]
    assert cached["schemas"][0]["cached"] is True
    row = db.get(MetadataCache, (connection_id, "main"))
    assert row is not None and row.size_bytes > 0 and len(row.payload) < row.size_bytes  # comprimido

    assert user_client.delete(f"{base}/main").status_code == 204
    db.expire_all()
    assert db.get(MetadataCache, (connection_id, "main")) is None


def test_table_detail_with_incoming_foreign_keys(user_client: TestClient, connection_id: int) -> None:
    base = f"/api/v1/connections/{connection_id}/metadata/schemas/main/tables"

    pedidos = user_client.get(f"{base}/pedidos").json()
    clientes = user_client.get(f"{base}/clientes").json()

    assert [c["name"] for c in pedidos["columns"]] == ["id", "cliente_id", "total"]
    assert pedidos["columns"][1]["nullable"] is False
    assert pedidos["primary_key"]["columns"] == ["id"]
    assert pedidos["foreign_keys"][0]["ref_table"] == "clientes"
    assert pedidos["foreign_keys"][0]["on_delete"] == "CASCADE"
    assert any(i["name"] == "ix_pedidos_cliente" for i in pedidos["indexes"])
    assert [fk["table"] for fk in clientes["referenced_by"]] == ["pedidos"]
    assert user_client.get(f"{base}/no_existe").status_code == 404


def test_ddl_of_table_and_view(user_client: TestClient, connection_id: int) -> None:
    base = f"/api/v1/connections/{connection_id}/metadata/schemas/main/ddl"

    table = user_client.get(base, params={"kind": "table", "name": "pedidos"}).json()
    view = user_client.get(base, params={"kind": "view", "name": "v_pedidos"}).json()

    assert table["ddl"].startswith("CREATE TABLE pedidos")
    assert view["ddl"].startswith("CREATE VIEW v_pedidos")
    assert user_client.get(base, params={"kind": "tabla", "name": "x"}).status_code == 422


def test_editing_connection_invalidates_cache(
    user_client: TestClient, connection_id: int, demo_db: str, db: Session
) -> None:
    user_client.get(f"/api/v1/connections/{connection_id}/metadata/schemas/main")

    user_client.patch(f"/api/v1/connections/{connection_id}", json={"params": {"database": demo_db, "timeout": 7}})

    db.expire_all()
    assert db.scalars(select(MetadataCache)).all() == []


def test_explorer_requires_visible_connection(
    user_client: TestClient, connection_id: int, make_user: Callable[..., User]
) -> None:
    other = login_as(user_client, make_user, "luis")
    base = f"/api/v1/connections/{connection_id}"

    for path in ["/metadata/schemas", "/metadata/schemas/main", "/metadata/schemas/main/tables/pedidos", "/queries"]:
        assert other.get(base + path).status_code == 404, path
    assert other.delete(f"{base}/metadata/schemas/main").status_code == 404


def test_missing_database_file_is_sanitized_502(user_client: TestClient, settings: Settings) -> None:
    connection = user_client.post(
        "/api/v1/connections", json={"name": "Nada", "db_type": "sqlite", "params": {"database": "no/existe.db"}}
    ).json()

    response = user_client.get(f"/api/v1/connections/{connection['id']}/metadata/schemas")

    assert response.status_code == 502
    assert response.json()["code"] == "connection_failed"
    assert str(settings.files_dir) not in response.text


# --- queries nombradas -------------------------------------------------------------------------------------------


QUERY = {
    "db_type": "sqlite",
    "name": "pedidos_por_cliente",
    "description": "Pedidos de un cliente",
    "sql_template": "SELECT id, total FROM {tabla} WHERE cliente_id = {cliente} ORDER BY id",
}


def test_named_queries_admin_crud(admin_client: TestClient, make_user: Callable[..., User]) -> None:
    regular = login_as(admin_client, make_user, "ana")
    assert regular.post("/api/v1/admin/queries", json=QUERY).status_code == 403

    created = admin_client.post("/api/v1/admin/queries", json=QUERY)

    assert created.status_code == 201, created.text
    assert created.json()["params"] == ["tabla", "cliente"]
    assert admin_client.post("/api/v1/admin/queries", json=QUERY).status_code == 409
    write = admin_client.post("/api/v1/admin/queries", json={**QUERY, "name": "x", "sql_template": "DELETE FROM {t}"})
    assert write.status_code == 422
    assert write.json()["errors"][0]["loc"] == ["body", "sql_template"]
    assert admin_client.post("/api/v1/admin/queries", json={**QUERY, "name": "y", "db_type": "db2"}).status_code == 404
    query_id = created.json()["id"]
    renamed = admin_client.patch(f"/api/v1/admin/queries/{query_id}", json={"description": "Otra"})
    assert renamed.json()["description"] == "Otra"
    assert admin_client.delete(f"/api/v1/admin/queries/{query_id}").status_code == 204
    assert admin_client.get("/api/v1/admin/queries").json() == []


def test_run_named_query(admin_client: TestClient, demo_db: str, db: Session) -> None:
    query_id = admin_client.post("/api/v1/admin/queries", json=QUERY).json()["id"]
    connection_id = admin_client.post(
        "/api/v1/connections", json={"name": "T", "db_type": "sqlite", "params": {"database": demo_db}}
    ).json()["id"]
    base = f"/api/v1/connections/{connection_id}/queries"

    listed = admin_client.get(base).json()
    ok = admin_client.post(f"{base}/{query_id}/run", json={"params": {"tabla": "pedidos", "cliente": 1}, "limit": 1})
    injection = admin_client.post(
        f"{base}/{query_id}/run", json={"params": {"tabla": "pedidos", "cliente": "1 OR 1=1"}}
    )
    missing = admin_client.post(f"{base}/{query_id}/run", json={"params": {"tabla": "pedidos"}})

    assert [q["name"] for q in listed] == ["pedidos_por_cliente"]
    assert ok.status_code == 200, ok.text
    assert ok.json() == {
        **ok.json(),
        "columns": ["id", "total"],
        "rows": [[10, 9.5]],
        "truncated": True,
        "row_count": 1,
    }
    assert injection.status_code == 422
    assert injection.json()["errors"][0]["loc"] == ["body", "params", "cliente"]
    assert missing.status_code == 422
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "query.execute")).first()
    assert entry is not None and entry.details == {
        "query": "pedidos_por_cliente",
        "params": {"tabla": "pedidos", "cliente": "1"},
    }


# --- SQL libre ---------------------------------------------------------------------------------------------------


@pytest.fixture
def sql_project(user_client: TestClient, user: User, connection_id: int, admin: User, db: Session) -> dict[str, object]:
    project = new_project(user_client, "Análisis")
    link = {"connection_id": connection_id, "alias": "tienda"}
    assert user_client.post(f"/api/v1/projects/{project['id']}/connections", json=link).status_code == 201
    return project


def grant_sql(client: TestClient, user: User) -> None:
    admin = TestClient(client.app, base_url="https://testserver")
    do_login(admin, "admin", "admin-password-1234")
    assert admin.patch(f"/api/v1/users/{user.id}", json={"can_run_sql": True}).json()["can_run_sql"] is True


def test_free_sql_requires_permission(user_client: TestClient, user: User, sql_project: dict[str, object]) -> None:
    url = f"/api/v1/projects/{sql_project['id']}/connections/tienda/sql"

    caps = user_client.get(f"/api/v1/projects/{sql_project['id']}/sql").json()
    denied = user_client.post(url, json={"sql": "SELECT 1"})

    assert caps["allowed"] is False and caps["reason"] == "permission"
    assert caps["connections"] == [
        {"alias": "tienda", "connection_name": "Tienda", "db_type": "sqlite", "read_only": True, "supported": True,
         "read_only_transaction": True}
    ]  # fmt: skip
    assert denied.status_code == 403


def test_free_sql_runs_read_only_queries(
    user_client: TestClient, user: User, sql_project: dict[str, object], db: Session, settings: Settings
) -> None:
    grant_sql(user_client, user)
    url = f"/api/v1/projects/{sql_project['id']}/connections/tienda/sql"

    ok = user_client.post(
        url,
        json={
            "sql": "SELECT c.nombre, SUM(p.total) AS t FROM clientes c JOIN pedidos p ON p.cliente_id = c.id GROUP BY c.nombre ORDER BY 1"
        },
    )
    limited = user_client.post(url, json={"sql": "SELECT * FROM pedidos", "limit": 2})
    delete = user_client.post(url, json={"sql": "DELETE FROM pedidos"})
    stacked = user_client.post(url, json={"sql": "SELECT 1; DROP TABLE pedidos"})
    engine_error = user_client.post(url, json={"sql": "SELECT * FROM no_existe"})

    assert ok.status_code == 200, ok.text
    assert ok.json()["columns"] == ["nombre", "t"]
    assert ok.json()["rows"] == [["ana", 29.5], ["luis", 3.25]]
    assert (limited.json()["row_count"], limited.json()["truncated"]) == (2, True)
    assert delete.status_code == 422 and delete.json()["code"] == "not_read_only"
    assert stacked.status_code == 422
    assert engine_error.status_code == 422
    assert engine_error.json() == {**engine_error.json(), "code": "query_error", "detail": "no such table: no_existe"}
    actions = db.scalars(select(AuditEntry).where(AuditEntry.action == "sql.execute").order_by(AuditEntry.id)).all()
    assert [a.outcome for a in actions] == ["success", "success", "failure", "failure", "failure"]
    assert actions[0].details is not None and actions[0].details["sql"].startswith("SELECT c.nombre")
    con = sqlite3.connect(settings.files_dir / "tienda.db")
    assert con.execute("SELECT COUNT(*) FROM pedidos").fetchone() == (3,)  # nada se ha borrado
    con.close()


def test_free_sql_needs_read_only_connection_and_editor(
    user_client: TestClient,
    user: User,
    sql_project: dict[str, object],
    connection_id: int,
    make_user: Callable[..., User],
) -> None:
    grant_sql(user_client, user)
    url = f"/api/v1/projects/{sql_project['id']}/connections/tienda/sql"
    user_client.patch(f"/api/v1/connections/{connection_id}", json={"read_only": False})

    assert user_client.post(url, json={"sql": "SELECT 1"}).status_code == 409

    viewer = login_as(user_client, make_user, "vera")
    user_client.post(f"/api/v1/projects/{sql_project['id']}/members", json={"username": "vera"})
    assert viewer.post(url, json={"sql": "SELECT 1"}).status_code == 403
    assert viewer.get(f"/api/v1/projects/{sql_project['id']}/sql").json()["reason"] == "role"
    outsider = login_as(user_client, make_user, "olga")
    assert outsider.post(url, json={"sql": "SELECT 1"}).status_code == 404
    assert (
        user_client.post(
            f"/api/v1/projects/{sql_project['id']}/connections/otra/sql", json={"sql": "SELECT 1"}
        ).status_code
        == 404
    )


def test_free_sql_timeout(
    user_client: TestClient,
    user: User,
    sql_project: dict[str, object],
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    grant_sql(user_client, user)
    monkeypatch.setattr(settings, "query_timeout_seconds", 1.0)
    slow = "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) SELECT count(*) FROM n"

    response = user_client.post(f"/api/v1/projects/{sql_project['id']}/connections/tienda/sql", json={"sql": slow})

    assert response.status_code == 504
    assert response.json()["code"] == "timeout"


def test_admin_toggles_sql_permission_and_me_reports_it(
    user_client: TestClient, user: User, db: Session, admin: User
) -> None:
    assert user_client.get("/api/v1/auth/me").json()["can_run_sql"] is False

    grant_sql(user_client, user)

    assert user_client.get("/api/v1/auth/me").json()["can_run_sql"] is True
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "user.update")).one()
    assert entry.details == {"fields": ["can_run_sql"], "can_run_sql": True}


def test_user_cannot_grant_itself(user_client: TestClient, user: User) -> None:
    assert user_client.patch(f"/api/v1/users/{user.id}", json={"can_run_sql": True}).status_code == 403
