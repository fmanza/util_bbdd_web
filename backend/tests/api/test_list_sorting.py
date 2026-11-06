"""Listas paginadas con orden por columna (lista blanca), desempate estable y búsqueda (sesión
``2026-11-06-explorer-runs-lists``, bloque C)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from app.db.models import User
from tests.api.test_connections import PG
from tests.api.test_projects import login_as, new_project
from tests.api.test_runs import launch


def _ids(client: TestClient, url: str, key: str = "id", **params: Any) -> list[Any]:
    response = client.get(url, params=params)
    assert response.status_code == 200, response.text
    return [item[key] for item in response.json()["items"]]


def test_users_sort_and_escaped_search(admin_client: TestClient, make_user: Callable[..., User]) -> None:
    for name in ("carla", "bea", "a_b"):
        make_user(name)

    names = _ids(admin_client, "/api/v1/users", "username", sort="username", order="desc")
    assert names == sorted(names, reverse=True)
    assert _ids(admin_client, "/api/v1/users", "username", sort="username") == sorted(names)
    # «_» es literal: no casa con cualquier carácter.
    assert _ids(admin_client, "/api/v1/users", "username", q="a_") == ["a_b"]
    assert admin_client.get("/api/v1/users", params={"sort": "password_hash"}).status_code == 422
    assert admin_client.get("/api/v1/users", params={"order": "sideways"}).status_code == 422


def test_paging_is_stable_with_ties(admin_client: TestClient, make_user: Callable[..., User]) -> None:
    for i in range(7):
        make_user(f"u{i}", role="user")
    # Todos con el mismo rol: el desempate por id evita repetir o saltar filas entre páginas.
    pages = [
        _ids(admin_client, "/api/v1/users", sort="role", order="asc", limit=3, offset=offset) for offset in (0, 3, 6)
    ]
    flat = [i for page in pages for i in page]
    assert len(flat) == len(set(flat)) == admin_client.get("/api/v1/users").json()["total"]


def test_sessions_and_audit_search_and_sort(admin_client: TestClient, make_user: Callable[..., User]) -> None:
    login_as(admin_client, make_user, "luisa")

    users = _ids(admin_client, "/api/v1/sessions", "username", sort="user", order="asc")
    assert users == sorted(users)
    assert _ids(admin_client, "/api/v1/sessions", "username", q="luis") == ["luisa"]
    assert admin_client.get("/api/v1/sessions", params={"sort": "token"}).status_code == 422

    actions = _ids(admin_client, "/api/v1/audit", "action", sort="action", order="asc")
    assert actions == sorted(actions)
    assert set(_ids(admin_client, "/api/v1/audit", "actor_username", q="luisa")) == {"luisa"}
    assert admin_client.get("/api/v1/audit", params={"sort": "details"}).status_code == 422


def test_connections_projects_runs_and_usage_sort(user_client: TestClient, admin: User) -> None:
    for name in ("zeta", "alfa", "Media"):
        assert user_client.post("/api/v1/connections", json={**PG, "name": name}).status_code == 201
    assert _ids(user_client, "/api/v1/connections", "name", sort="name") == ["alfa", "Media", "zeta"]
    assert _ids(user_client, "/api/v1/connections", "name", sort="name", order="desc") == ["zeta", "Media", "alfa"]

    for name in ("Beta", "alfa"):
        new_project(user_client, name)
    assert _ids(user_client, "/api/v1/projects", "name", sort="name", order="desc") == ["Beta", "alfa"]

    project = new_project(user_client, "Con ejecuciones")
    first = launch(user_client, project["id"], steps=1, step_seconds=0)["id"]
    second = launch(user_client, project["id"], steps=1, step_seconds=0)["id"]
    url = f"/api/v1/projects/{project['id']}/runs"
    assert _ids(user_client, url) == [second, first]  # por defecto, las más recientes primero
    assert _ids(user_client, url, sort="created_at", order="asc") == [first, second]
    assert _ids(user_client, "/api/v1/runs", sort="created_at", order="asc") == [first, second]
    assert user_client.get(url, params={"sort": "params"}).status_code == 422


def test_storage_usage_sort(admin_client: TestClient, make_user: Callable[..., User]) -> None:
    for name in ("zoe", "ana2"):
        make_user(name)
    names = _ids(admin_client, "/api/v1/admin/storage/usage", "username", sort="username")
    assert names == sorted(names, key=str.lower)
    assert _ids(admin_client, "/api/v1/admin/storage/usage", "username", sort="username", order="desc") == names[::-1]
    assert admin_client.get("/api/v1/admin/storage/usage", params={"sort": "email"}).status_code == 422
