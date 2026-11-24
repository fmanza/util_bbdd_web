"""Alta con opciones, filtros por rol y estado, desbloqueo y borrado de usuarios (ADR-013)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, Connection, User, UserSession, utcnow
from app.domain.identity import users as users_module
from app.domain.identity.audit import CLI_CONTEXT
from app.domain.identity.errors import LastAdminError
from app.domain.identity.users import UserChanges, update_user
from tests.api.test_connections import PG
from tests.api.test_projects import login_as, new_project
from tests.conftest import USER_PASSWORD, do_login

NEW_USER = {"username": "luis", "display_name": "Luis", "password": "luis-frase-de-paso"}


def _usernames(client: TestClient, **params: object) -> list[str]:
    response = client.get("/api/v1/users", params=params)
    assert response.status_code == 200, response.text
    return [u["username"] for u in response.json()["items"]]


# --- alta con opciones ---------------------------------------------------------------------------------------------


def test_create_user_with_all_options_is_audited(admin_client: TestClient, db: Session) -> None:
    body = {
        **NEW_USER,
        "role": "user",
        "is_active": False,
        "can_run_sql": True,
        "can_apply_ddl": True,
        "can_write_data": False,
        "storage_quota_mb": 0,
    }

    created = admin_client.post("/api/v1/users", json=body)

    assert created.status_code == 201, created.text
    user = created.json()
    assert (user["is_active"], user["can_run_sql"], user["can_apply_ddl"], user["can_write_data"]) == (
        False,
        True,
        True,
        False,
    )
    assert user["storage_quota_mb"] == 0
    assert user["project_count"] == 0
    entry = db.scalars(
        select(AuditEntry).where(AuditEntry.action == "user.create", AuditEntry.target_id == str(user["id"]))
    ).one()
    assert entry.details is not None
    assert entry.details["can_apply_ddl"] is True and entry.details["is_active"] is False
    assert "password" not in str(entry.details)


def test_create_user_defaults_are_unchanged(admin_client: TestClient) -> None:
    user = admin_client.post("/api/v1/users", json=NEW_USER).json()

    assert user["role"] == "user" and user["is_active"] is True
    assert not (user["can_run_sql"] or user["can_apply_ddl"] or user["can_write_data"])
    assert user["storage_quota_mb"] is None
    assert admin_client.post("/api/v1/users", json={**NEW_USER, "storage_quota_mb": -1}).status_code == 422


# --- filtros, número de proyectos y administradores activos --------------------------------------------------------


def test_filter_by_role_and_status(admin_client: TestClient, make_user: Callable[..., User], db: Session) -> None:
    make_user("bea")
    make_user("carla", role="admin")
    inactive = make_user("dani")
    inactive.is_active = False
    locked = make_user("eva")
    locked.locked_until = utcnow() + timedelta(minutes=10)
    expired = make_user("fran")
    expired.locked_until = utcnow() - timedelta(minutes=10)
    db.commit()

    assert _usernames(admin_client, role="admin") == ["admin", "carla"]
    assert _usernames(admin_client, status="inactive") == ["dani"]
    assert _usernames(admin_client, status="locked") == ["eva"]
    assert _usernames(admin_client, status="active") == ["admin", "bea", "carla", "fran"]
    assert _usernames(admin_client, role="user", status="active", q="b") == ["bea"]
    assert admin_client.get("/api/v1/users", params={"status": "borrado"}).status_code == 422
    assert admin_client.get("/api/v1/users", params={"role": "root"}).status_code == 422
    assert admin_client.get("/api/v1/users").json()["active_admins"] == 2


def test_project_count_and_sort(admin_client: TestClient, make_user: Callable[..., User]) -> None:
    luis = login_as(admin_client, make_user, "luis")
    new_project(luis, "Uno")
    new_project(luis, "Dos")
    make_user("mar")

    items = admin_client.get("/api/v1/users", params={"sort": "projects", "order": "desc"}).json()["items"]

    assert [(u["username"], u["project_count"]) for u in items][0] == ("luis", 2)
    assert {u["username"]: u["project_count"] for u in items}["mar"] == 0
    luis_id = next(u["id"] for u in items if u["username"] == "luis")
    assert admin_client.get(f"/api/v1/users/{luis_id}").json()["project_count"] == 2


# --- desbloqueo ----------------------------------------------------------------------------------------------------


def test_unlock_user(admin_client: TestClient, user: User, db: Session) -> None:
    user.failed_attempts = 5
    user.locked_until = utcnow() + timedelta(minutes=10)
    db.commit()

    response = admin_client.post(f"/api/v1/users/{user.id}/unlock")

    assert response.status_code == 200
    assert response.json()["locked_until"] is None
    db.refresh(user)
    assert user.failed_attempts == 0
    assert db.scalars(select(AuditEntry).where(AuditEntry.action == "user.unlock")).one().target_id == str(user.id)
    ana = TestClient(admin_client.app, base_url="https://testserver")
    do_login(ana, "ana", USER_PASSWORD)
    # Sin bloqueo que quitar no se audita otra vez.
    admin_client.post(f"/api/v1/users/{user.id}/unlock")
    assert len(db.scalars(select(AuditEntry).where(AuditEntry.action == "user.unlock")).all()) == 1
    assert admin_client.post("/api/v1/users/9999/unlock").status_code == 404


# --- borrado -------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [("DELETE", "/api/v1/users/1"), ("GET", "/api/v1/users/1/deletion-check"), ("POST", "/api/v1/users/1/unlock")],
)
def test_new_endpoints_are_admin_only(user_client: TestClient, method: str, path: str) -> None:
    assert user_client.request(method, path).status_code == 403


def test_delete_requires_csrf(admin_client: TestClient, user: User) -> None:
    del admin_client.headers["X-CSRF-Token"]

    assert admin_client.delete(f"/api/v1/users/{user.id}").status_code == 403


def test_delete_user_without_dependencies(
    admin_client: TestClient, make_user: Callable[..., User], db: Session, migrated: Settings
) -> None:
    luis = login_as(admin_client, make_user, "luis")
    assert luis.post("/api/v1/connections", json=PG).status_code == 201
    luis_id = db.scalars(select(User.id).where(User.username == "luis")).one()
    folder = Path(migrated.workspace_dir) / "users" / str(luis_id)
    folder.mkdir(parents=True)

    check = admin_client.get(f"/api/v1/users/{luis_id}/deletion-check").json()
    assert check == {"can_delete": True, "reasons": [], "projects": [], "created_projects": [], "connections": []}

    assert admin_client.delete(f"/api/v1/users/{luis_id}").status_code == 204

    db.expire_all()
    assert db.get(User, luis_id) is None
    assert db.scalars(select(UserSession).where(UserSession.user_id == luis_id)).all() == []
    assert db.scalars(select(Connection).where(Connection.owner_id == luis_id)).all() == []
    assert luis.get("/api/v1/auth/me").status_code == 401
    assert not folder.exists()
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "user.delete")).one()
    assert entry.details == {"username": "luis", "role": "user", "connections_deleted": 1}
    # Sus acciones pasadas siguen atribuidas por nombre.
    logins = admin_client.get("/api/v1/audit", params={"action": "auth.login", "q": "luis"}).json()["items"]
    assert [e["actor_username"] for e in logins] == ["luis"]
    assert admin_client.delete(f"/api/v1/users/{luis_id}").status_code == 404


def test_delete_blocked_by_membership_creation_and_connections(
    admin_client: TestClient, make_user: Callable[..., User], db: Session
) -> None:
    luis = login_as(admin_client, make_user, "luis")
    created = new_project(luis, "Suyo")
    other = login_as(admin_client, make_user, "mar")
    shared = new_project(other, "Compartido")
    assert (
        other.post(f"/api/v1/projects/{shared['id']}/members", json={"username": "luis", "role": "editor"}).status_code
        == 201
    )
    connection_id = luis.post("/api/v1/connections", json=PG).json()["id"]
    luis.post(f"/api/v1/projects/{created['id']}/connections", json={"connection_id": connection_id, "alias": "o"})
    luis_id = db.scalars(select(User.id).where(User.username == "luis")).one()

    check = admin_client.get(f"/api/v1/users/{luis_id}/deletion-check").json()
    response = admin_client.delete(f"/api/v1/users/{luis_id}")

    assert check["can_delete"] is False
    assert check["reasons"] == ["member", "creator", "connections"]
    assert check["projects"] == [
        {"id": shared["id"], "name": "Compartido", "role": "editor"},
        {"id": created["id"], "name": "Suyo", "role": "owner"},
    ]
    assert check["created_projects"] == [{"id": created["id"], "name": "Suyo", "role": None}]
    assert check["connections"] == [{"id": connection_id, "name": "Ventas", "visibility": "private"}]
    assert response.status_code == 409
    problem = response.json()
    assert problem["reasons"] == check["reasons"] and problem["projects"] == check["projects"]
    assert "pg-secreta" not in response.text
    db.expire_all()
    assert db.get(User, luis_id) is not None


def test_creator_without_membership_still_blocks(admin_client: TestClient, make_user: Callable[..., User]) -> None:
    """Quien creó un proyecto lo bloquea aunque ya no sea miembro: la carpeta del proyecto cuelga de la suya."""
    luis = login_as(admin_client, make_user, "luis")
    project = new_project(luis, "Heredado")
    make_user("mar")
    luis.post(f"/api/v1/projects/{project['id']}/members", json={"username": "mar", "role": "owner"})
    luis_id = luis.get("/api/v1/auth/me").json()["id"]
    assert luis.delete(f"/api/v1/projects/{project['id']}/members/{luis_id}").status_code == 204

    check = admin_client.get(f"/api/v1/users/{luis_id}/deletion-check").json()

    assert check["reasons"] == ["creator"]
    assert check["created_projects"] == [{"id": project["id"], "name": "Heredado", "role": None}]
    assert admin_client.delete(f"/api/v1/users/{luis_id}").status_code == 409


def test_cannot_delete_self_or_last_admin(
    admin_client: TestClient, admin: User, make_user: Callable[..., User]
) -> None:
    response = admin_client.delete(f"/api/v1/users/{admin.id}")
    assert response.status_code == 409
    assert response.json()["title"] == "No puedes eliminar tu propia cuenta"
    assert admin_client.get(f"/api/v1/users/{admin.id}/deletion-check").json()["reasons"] == ["self", "last_admin"]

    other = make_user("jefa", role="admin")
    assert admin_client.get(f"/api/v1/users/{other.id}/deletion-check").json()["can_delete"] is True
    assert admin_client.delete(f"/api/v1/users/{other.id}").status_code == 204


def test_last_active_admin_cannot_be_deleted_by_another_admin(
    admin_client: TestClient, admin: User, make_user: Callable[..., User], db: Session
) -> None:
    jefa = make_user("jefa", role="admin")
    # «admin» deja de ser admin activo sin pasar por la API (p. ej. otra petición simultánea).
    jefa_client = TestClient(admin_client.app, base_url="https://testserver")
    do_login(jefa_client, "jefa", USER_PASSWORD)
    admin.is_active = False
    db.commit()

    assert jefa_client.get(f"/api/v1/users/{jefa.id}/deletion-check").json()["reasons"] == ["self", "last_admin"]
    assert jefa_client.delete(f"/api/v1/users/{admin.id}").status_code == 204  # un admin inactivo sí se borra
    assert jefa_client.patch(f"/api/v1/users/{jefa.id}", json={"is_active": False}).status_code == 409


def test_recount_after_write_keeps_one_active_admin(
    db: Session, admin: User, make_user: Callable[..., User], migrated: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Carrera: la comprobación previa ve dos admins activos (otra petición aún no había confirmado su cambio), pero
    al escribir ya solo queda uno: el recuento posterior lo detecta y deshace."""
    jefa = make_user("jefa", role="admin")
    jefa.is_active = False
    db.commit()
    real = users_module.count_active_admins
    stale = iter([2])
    monkeypatch.setattr(users_module, "count_active_admins", lambda session: next(stale, None) or real(session))

    with pytest.raises(LastAdminError):
        update_user(db, admin, UserChanges(is_active=False), actor=jefa, settings=migrated, ctx=CLI_CONTEXT)

    db.expire_all()
    assert db.get(User, admin.id).is_active is True  # type: ignore[union-attr]
