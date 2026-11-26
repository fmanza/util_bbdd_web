"""Roles y permisos (ADR-014): API, salvaguardas, cierre de sesiones, columnas antiguas y migración 0014."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, Role, User
from app.db.session import get_engine
from app.domain.identity.permissions import PERMISSIONS
from app.domain.identity.roles import builtin_role
from tests.api.test_projects import login_as
from tests.conftest import USER_PASSWORD, do_login, grant, run_migrations


def _roles(client: TestClient) -> dict[str, dict[str, object]]:
    response = client.get("/api/v1/roles")
    assert response.status_code == 200, response.text
    return {r["name"]: r for r in response.json()}


# --- catálogo y roles base -----------------------------------------------------------------------------------------


def test_catalog_and_builtin_roles(admin_client: TestClient, user: User) -> None:
    catalog = admin_client.get("/api/v1/roles/permissions").json()
    assert [p["name"] for p in catalog] == list(PERMISSIONS)
    assert {p["name"] for p in catalog if p["group"] == "databases"} == {
        "connections.share",
        "sql.run",
        "ddl.apply",
        "data.write",
    }

    roles = _roles(admin_client)
    assert list(roles)[:2] == ["Administrador", "Usuario"]
    assert roles["Administrador"]["permissions"] == list(PERMISSIONS)
    assert roles["Administrador"]["user_count"] == 1 and roles["Usuario"]["user_count"] == 1
    assert roles["Usuario"]["permissions"] == []


def test_roles_require_roles_or_users_manage(user_client: TestClient, db: Session, user: User) -> None:
    assert user_client.get("/api/v1/roles").status_code == 403
    assert user_client.post("/api/v1/roles", json={"name": "X", "permissions": []}).status_code == 403

    grant(db, user, "users.manage")
    do_login(user_client, "ana", USER_PASSWORD)
    assert user_client.get("/api/v1/roles").status_code == 200  # para poder asignarlos
    assert user_client.post("/api/v1/roles", json={"name": "X", "permissions": []}).status_code == 403


# --- crear, editar y borrar ----------------------------------------------------------------------------------------


def test_create_update_delete_is_audited(admin_client: TestClient, db: Session) -> None:
    created = admin_client.post("/api/v1/roles", json={"name": " Auditores ", "permissions": ["audit.read", "sql.run"]})
    assert created.status_code == 201, created.text
    role = created.json()
    # Se guardan en el orden del catálogo.
    assert role["name"] == "Auditores" and role["permissions"] == ["audit.read", "sql.run"] and role["builtin"] is None

    assert admin_client.post("/api/v1/roles", json={"name": "auditores"}).status_code == 409
    assert admin_client.post("/api/v1/roles", json={"name": "Y", "permissions": ["root"]}).status_code == 422

    updated = admin_client.patch(
        f"/api/v1/roles/{role['id']}", json={"name": "Lectores", "permissions": ["audit.read"]}
    )
    assert updated.status_code == 200 and updated.json()["permissions"] == ["audit.read"]

    assert admin_client.delete(f"/api/v1/roles/{role['id']}").status_code == 204
    actions = [e.action for e in db.scalars(select(AuditEntry).where(AuditEntry.target_type == "role"))]
    assert actions == ["role.create", "role.update", "role.delete"]


def test_builtin_roles_cannot_be_changed_renamed_or_deleted(admin_client: TestClient, db: Session) -> None:
    user_role = builtin_role(db, "user").id
    admin_role = builtin_role(db, "admin").id

    assert admin_client.patch(f"/api/v1/roles/{user_role}", json={"permissions": ["sql.run"]}).status_code == 409
    assert admin_client.patch(f"/api/v1/roles/{user_role}", json={"name": "Básico"}).status_code == 409
    assert admin_client.delete(f"/api/v1/roles/{admin_role}").status_code == 409
    # Enviar el mismo nombre y los mismos permisos de un rol base no es un cambio.
    same = admin_client.patch(
        f"/api/v1/roles/{admin_role}", json={"name": "Administrador", "permissions": list(PERMISSIONS)}
    )
    assert same.status_code == 200


def test_role_with_users_is_not_deleted(admin_client: TestClient, db: Session, user: User) -> None:
    role = admin_client.post("/api/v1/roles", json={"name": "SQL", "permissions": ["sql.run"]}).json()
    admin_client.patch(f"/api/v1/users/{user.id}", json={"role_id": role["id"]})

    assert admin_client.delete(f"/api/v1/roles/{role['id']}").status_code == 409
    assert _roles(admin_client)["SQL"]["user_count"] == 1
    assert admin_client.delete("/api/v1/roles/9999").status_code == 404


# --- escalada de permisos --------------------------------------------------------------------------------------------


def test_nobody_grants_what_they_do_not_have(
    client: TestClient, db: Session, make_user: Callable[..., User], admin: User
) -> None:
    jefe = make_user("jefe")
    grant(db, jefe, "roles.manage", "users.manage", "audit.read")
    victim = make_user("vic")
    jefe_client = login_as(client, make_user, "otro")  # cliente con sesión; se reutiliza para jefe
    do_login(jefe_client, "jefe", USER_PASSWORD)

    # Crear un rol con un permiso que no tiene.
    assert jefe_client.post("/api/v1/roles", json={"name": "SQL", "permissions": ["sql.run"]}).status_code == 403
    ok = jefe_client.post("/api/v1/roles", json={"name": "Auditor", "permissions": ["audit.read"]})
    assert ok.status_code == 201

    # Asignar a otro un rol con permisos que no tiene (el base «Administrador»).
    admin_role = builtin_role(db, "admin").id
    assert jefe_client.patch(f"/api/v1/users/{victim.id}", json={"role_id": admin_role}).status_code == 403
    assert (
        jefe_client.post(
            "/api/v1/users",
            json={"username": "nuevo", "display_name": "N", "password": "frase-de-paso-larga", "role_id": admin_role},
        ).status_code
        == 403
    )
    # Ni cambiar el rol de quien tiene más permisos (el admin).
    assert jefe_client.patch(f"/api/v1/users/{admin.id}", json={"role_id": ok.json()["id"]}).status_code == 403
    # Lo que sí tiene, sí.
    assert jefe_client.patch(f"/api/v1/users/{victim.id}", json={"role_id": ok.json()["id"]}).status_code == 200
    # Ni cambiarse el propio rol.
    assert jefe_client.patch(f"/api/v1/users/{jefe.id}", json={"role_id": ok.json()["id"]}).status_code == 409


def test_user_manager_cannot_act_on_someone_with_more_permissions(
    client: TestClient, db: Session, make_user: Callable[..., User], admin: User
) -> None:
    """Quien solo gestiona usuarios no restablece la contraseña de un admin (y entra como él), ni lo desactiva, borra o
    le transfiere/quita lo suyo."""
    manager = make_user("gestor")
    grant(db, manager, "users.manage")
    peer = make_user("par")
    gestor = TestClient(client.app, base_url="https://testserver")
    do_login(gestor, "gestor", USER_PASSWORD)

    assert gestor.patch(f"/api/v1/users/{admin.id}", json={"password": "otra-frase-de-paso-larga"}).status_code == 403
    assert gestor.patch(f"/api/v1/users/{admin.id}", json={"is_active": False}).status_code == 403
    assert gestor.get(f"/api/v1/users/{admin.id}/deletion-check").status_code == 403
    assert gestor.delete(f"/api/v1/users/{admin.id}").status_code == 403
    preview = f"/api/v1/users/{peer.id}/transfer-preview?target_user_id={admin.id}"
    assert gestor.get(preview).status_code == 403
    # Sobre quien no tiene más permisos, sí.
    assert gestor.patch(f"/api/v1/users/{peer.id}", json={"display_name": "Par"}).status_code == 200


def test_removing_permissions_closes_sessions(admin_client: TestClient, db: Session, user: User) -> None:
    role = admin_client.post("/api/v1/roles", json={"name": "Datos", "permissions": ["data.write", "sql.run"]}).json()
    admin_client.patch(f"/api/v1/users/{user.id}", json={"role_id": role["id"]})
    ana = TestClient(admin_client.app, base_url="https://testserver")
    do_login(ana, "ana", USER_PASSWORD)

    # Añadir no cierra sesiones; quitar, sí.
    admin_client.patch(f"/api/v1/roles/{role['id']}", json={"permissions": ["data.write", "ddl.apply", "sql.run"]})
    assert ana.get("/api/v1/auth/me").status_code == 200
    admin_client.patch(f"/api/v1/roles/{role['id']}", json={"permissions": ["ddl.apply"]})
    assert ana.get("/api/v1/auth/me").status_code == 401


def test_last_admin_rule_uses_the_admin_role(
    admin_client: TestClient, db: Session, admin: User, make_user: Callable[..., User]
) -> None:
    other = make_user("otra", USER_PASSWORD, "admin")
    user_role = builtin_role(db, "user").id

    assert admin_client.patch(f"/api/v1/users/{other.id}", json={"role_id": user_role}).status_code == 200
    page = admin_client.get("/api/v1/users").json()
    assert page["active_admins"] == 1


def test_permission_dependency_gates_admin_areas(user_client: TestClient, db: Session, user: User) -> None:
    areas = {
        "audit.read": "/api/v1/audit",
        "sessions.manage": "/api/v1/sessions",
        "users.manage": "/api/v1/users",
        "allowlist.manage": "/api/v1/admin/allowlist",
        "queries.manage": "/api/v1/admin/queries",
        "storage.manage": "/api/v1/admin/storage",
        "runs.admin": "/api/v1/admin/runs",
    }
    for path in areas.values():
        assert user_client.get(path).status_code == 403, path

    grant(db, user, "audit.read")
    do_login(user_client, "ana", USER_PASSWORD)
    assert user_client.get(areas["audit.read"]).status_code == 200
    assert user_client.get(areas["users.manage"]).status_code == 403


# --- migración 0014 ------------------------------------------------------------------------------------------------


def test_migration_0014_keeps_each_users_permissions(settings: Settings) -> None:
    run_migrations("0013")
    rows = [
        (1, "jefa", "admin", 0, 0, 0),
        (2, "ana", "user", 0, 0, 0),
        (3, "sql", "user", 1, 0, 0),
        (4, "sql2", "user", 1, 0, 0),
        (5, "todo", "user", 1, 1, 1),
    ]
    with get_engine().begin() as connection:
        for uid, name, role, sql, ddl, data in rows:
            connection.execute(
                text(
                    "INSERT INTO users (id, username, display_name, password_hash, role, is_active, failed_attempts, "
                    "can_run_sql, can_apply_ddl, can_write_data, password_changed_at, created_at, updated_at) "
                    "VALUES (:id, :n, :n, 'x', :r, 1, 0, :s, :d, :w, '2026-11-01', '2026-11-01', '2026-11-01')"
                ),
                {"id": uid, "n": name, "r": role, "s": sql, "d": ddl, "w": data},
            )

    run_migrations()

    with Session(get_engine()) as db:
        users = {u.username: u for u in db.scalars(select(User))}
        assert users["jefa"].is_admin and users["jefa"].permissions == list(PERMISSIONS)
        assert users["ana"].role.builtin == "user" and users["ana"].permissions == []
        assert users["sql"].role.name == "Usuario + SQL" and users["sql"].permissions == ["sql.run"]
        assert users["sql2"].role_id == users["sql"].role_id  # una sola por combinación
        assert users["todo"].role.name == "Usuario + SQL + DDL + datos"
        assert users["todo"].permissions == ["sql.run", "ddl.apply", "data.write"]
        assert db.scalar(select(Role).where(Role.builtin == "admin")) is not None


def test_migration_0014_downgrade_restores_columns(settings: Settings) -> None:
    from alembic import command
    from alembic.config import Config

    from tests.conftest import BACKEND_DIR

    run_migrations()
    with Session(get_engine()) as db:
        role = Role(name="DDL", permissions=["ddl.apply"])
        db.add(role)
        db.flush()
        db.execute(
            text(
                "INSERT INTO users (username, display_name, password_hash, role_id, is_active, failed_attempts, "
                "password_changed_at, created_at, updated_at) "
                "VALUES ('eva', 'Eva', 'x', :r, 1, 0, '2026-11-01', '2026-11-01', '2026-11-01')"
            ),
            {"r": role.id},
        )
        db.commit()

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.downgrade(config, "0013")

    with get_engine().connect() as connection:
        row = connection.execute(
            text("SELECT role, can_run_sql, can_apply_ddl, can_write_data FROM users WHERE username = 'eva'")
        ).one()
        assert tuple(row) == ("user", 0, 1, 0)
        tables = {r[0] for r in connection.execute(text("SELECT name FROM sqlite_master WHERE type = 'table'"))}
        assert "roles" not in tables


@pytest.mark.parametrize("language", ["es", "en"])
def test_language_preference(client: TestClient, user: User, db: Session, language: str) -> None:
    do_login(client, "ana", USER_PASSWORD)

    response = client.patch("/api/v1/auth/me/preferences", json={"language": language})

    assert response.status_code == 200 and response.json()["language"] == language
    assert response.json()["color_scheme"] == "auto"  # lo que no llega no cambia
    db.refresh(user)
    assert user.language == language
    assert client.patch("/api/v1/auth/me/preferences", json={"language": "fr"}).status_code == 422
