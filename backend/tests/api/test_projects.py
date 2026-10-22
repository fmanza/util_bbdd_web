"""Proyectos, miembros y conexiones del proyecto: roles, IDOR (404), último propietario y alias."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEntry, User
from tests.conftest import USER_PASSWORD, do_login

PG = {
    "name": "Ventas",
    "db_type": "postgresql",
    "params": {"host": "db.corp", "user": "u", "database": "d"},
    "password": "pg-secreta-123",
}


def login_as(client: TestClient, make_user: Callable[..., User], username: str, role: str = "user") -> TestClient:
    make_user(username, USER_PASSWORD, role)
    other = TestClient(client.app, base_url="https://testserver")
    do_login(other, username, USER_PASSWORD)
    return other


def new_project(client: TestClient, name: str = "Migración 2026") -> dict[str, object]:
    response = client.post("/api/v1/projects", json={"name": name, "description": "Pruebas"})
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


def test_create_and_list_projects(user_client: TestClient, db: Session) -> None:
    project = new_project(user_client)

    assert project["my_role"] == "owner"
    assert [p["name"] for p in user_client.get("/api/v1/projects").json()["items"]] == ["Migración 2026"]
    assert user_client.post("/api/v1/projects", json={"name": "migración 2026"}).status_code == 409
    assert user_client.post("/api/v1/projects", json={"name": ""}).status_code == 422
    assert db.scalars(select(AuditEntry.action).where(AuditEntry.action == "project.create")).all()


def test_projects_require_session(client: TestClient) -> None:
    assert client.get("/api/v1/projects").status_code == 401


def test_non_member_gets_404_everywhere(user_client: TestClient, make_user: Callable[..., User]) -> None:
    project_id = new_project(user_client)["id"]
    outsider = login_as(user_client, make_user, "luis")

    for method, path in [
        ("GET", f"/api/v1/projects/{project_id}"),
        ("PATCH", f"/api/v1/projects/{project_id}"),
        ("DELETE", f"/api/v1/projects/{project_id}"),
        ("GET", f"/api/v1/projects/{project_id}/members"),
        ("GET", f"/api/v1/projects/{project_id}/connections"),
        ("GET", f"/api/v1/projects/{project_id}/runs"),
        ("POST", f"/api/v1/projects/{project_id}/runs"),
    ]:
        assert outsider.request(method, path, json={"operation": "noop"}).status_code == 404, path
    assert outsider.get("/api/v1/projects").json()["total"] == 0


def test_admin_does_not_see_projects_of_others(user_client: TestClient, make_user: Callable[..., User]) -> None:
    project_id = new_project(user_client)["id"]
    admin = login_as(user_client, make_user, "jefa", "admin")

    assert admin.get(f"/api/v1/projects/{project_id}").status_code == 404


def test_members_roles_and_permissions(user_client: TestClient, make_user: Callable[..., User]) -> None:
    project_id = new_project(user_client)["id"]
    viewer = login_as(user_client, make_user, "vera")
    editor = login_as(user_client, make_user, "eduardo")

    assert (
        user_client.post(f"/api/v1/projects/{project_id}/members", json={"username": "Vera"}).json()["role"] == "viewer"
    )
    added = user_client.post(f"/api/v1/projects/{project_id}/members", json={"username": "eduardo", "role": "editor"})
    assert added.status_code == 201
    assert user_client.post(f"/api/v1/projects/{project_id}/members", json={"username": "vera"}).status_code == 409
    assert user_client.post(f"/api/v1/projects/{project_id}/members", json={"username": "nadie"}).status_code == 404

    assert viewer.get(f"/api/v1/projects/{project_id}").json()["my_role"] == "viewer"
    assert viewer.patch(f"/api/v1/projects/{project_id}", json={"name": "X"}).status_code == 403
    assert viewer.post(f"/api/v1/projects/{project_id}/runs", json={"operation": "noop"}).status_code == 403
    assert editor.post(f"/api/v1/projects/{project_id}/members", json={"username": "vera"}).status_code == 403
    assert editor.post(f"/api/v1/projects/{project_id}/runs", json={"operation": "noop"}).status_code == 202
    assert {m["username"] for m in viewer.get(f"/api/v1/projects/{project_id}/members").json()} == {
        "ana",
        "vera",
        "eduardo",
    }


def test_last_owner_is_protected_and_members_can_leave(
    user_client: TestClient, user: User, make_user: Callable[..., User]
) -> None:
    project_id = new_project(user_client)["id"]
    viewer = login_as(user_client, make_user, "vera")
    vera_id = user_client.post(f"/api/v1/projects/{project_id}/members", json={"username": "vera"}).json()["user_id"]

    assert (
        user_client.patch(f"/api/v1/projects/{project_id}/members/{user.id}", json={"role": "editor"}).status_code
        == 409
    )
    assert user_client.delete(f"/api/v1/projects/{project_id}/members/{user.id}").status_code == 409
    assert viewer.delete(f"/api/v1/projects/{project_id}/members/{user.id}").status_code == 403
    assert (
        user_client.patch(f"/api/v1/projects/{project_id}/members/{vera_id}", json={"role": "owner"}).status_code == 200
    )
    assert (
        user_client.patch(f"/api/v1/projects/{project_id}/members/{user.id}", json={"role": "viewer"}).status_code
        == 200
    )
    assert viewer.delete(f"/api/v1/projects/{project_id}/members/{vera_id}").status_code == 409  # última owner
    assert user_client.delete(f"/api/v1/projects/{project_id}/members/{user.id}").status_code == 204
    assert user_client.get(f"/api/v1/projects/{project_id}").status_code == 404


def test_project_connections_with_alias(user_client: TestClient, make_user: Callable[..., User]) -> None:
    project_id = new_project(user_client)["id"]
    connection_id = user_client.post("/api/v1/connections", json=PG).json()["id"]
    other = login_as(user_client, make_user, "luis")
    foreign_id = other.post("/api/v1/connections", json=PG).json()["id"]

    created = user_client.post(
        f"/api/v1/projects/{project_id}/connections", json={"connection_id": connection_id, "alias": "origen"}
    )
    assert created.status_code == 201, created.text
    assert created.json() == {
        **created.json(),
        "alias": "origen",
        "connection_name": "Ventas",
        "db_type": "postgresql",
        "read_only": True,
    }
    assert "pg-secreta-123" not in created.text
    dup = {"connection_id": connection_id, "alias": "origen"}
    assert user_client.post(f"/api/v1/projects/{project_id}/connections", json=dup).status_code == 409
    bad = {"connection_id": connection_id, "alias": "Con Espacios"}
    assert user_client.post(f"/api/v1/projects/{project_id}/connections", json=bad).status_code == 422
    foreign = {"connection_id": foreign_id, "alias": "ajena"}
    assert user_client.post(f"/api/v1/projects/{project_id}/connections", json=foreign).status_code == 404
    assert [c["alias"] for c in user_client.get(f"/api/v1/projects/{project_id}/connections").json()] == ["origen"]
    assert user_client.delete(f"/api/v1/projects/{project_id}/connections/origen").status_code == 204
    assert user_client.delete(f"/api/v1/projects/{project_id}/connections/origen").status_code == 404


@pytest.mark.parametrize("field", ["name", "description"])
def test_update_and_delete_project(user_client: TestClient, field: str) -> None:
    project_id = new_project(user_client)["id"]

    updated = user_client.patch(f"/api/v1/projects/{project_id}", json={field: "Nuevo"})

    assert updated.json()[field] == "Nuevo"
    assert user_client.delete(f"/api/v1/projects/{project_id}").status_code == 204
    assert user_client.get(f"/api/v1/projects/{project_id}").status_code == 404


def test_cannot_delete_project_with_active_runs(user_client: TestClient) -> None:
    project_id = new_project(user_client)["id"]
    user_client.post(f"/api/v1/projects/{project_id}/runs", json={"operation": "noop"})

    assert user_client.delete(f"/api/v1/projects/{project_id}").status_code == 409
