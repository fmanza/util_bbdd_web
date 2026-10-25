"""Almacenamiento administrable (ADR-012): ajustes con la variable ``UBW_*`` como valor por defecto, cuota por usuario,
purga por cuota (al encolar, al subir y en el worker), vista previa, «Aplicar ahora», uso por usuario y «Mi espacio»."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AppSetting, AuditEntry, Run, User, utcnow
from app.jobs.worker import Worker
from tests.api.test_projects import login_as, new_project
from tests.api.test_runs import launch

MB = 1024 * 1024
URL = "/api/v1/admin/storage"


def _admin(client: TestClient, make_user: Callable[..., User]) -> TestClient:
    return login_as(client, make_user, "root", role="admin")


def _finish(db: Session, run_id: object, *, size_mb: float = 1, ago: timedelta = timedelta(hours=2)) -> None:
    """Deja una ejecución como terminada hace ``ago`` y ocupando ``size_mb``."""
    db.execute(
        update(Run)
        .where(Run.id == run_id)
        .values(status="succeeded", finished_at=utcnow() - ago, size_bytes=int(size_mb * MB))
    )
    db.commit()


def _status(db: Session, run_id: object) -> str:
    db.expire_all()
    run = db.get(Run, run_id)
    assert run is not None
    return run.status


# --- ajustes -----------------------------------------------------------------------------------------------------


def test_settings_default_to_env_and_can_be_changed_and_reset(
    user_client: TestClient, make_user: Callable[..., User], db: Session
) -> None:
    admin = _admin(user_client, make_user)
    state = admin.get(URL).json()
    assert state["user_quota_mb"] == {"value": 1024, "default": 1024, "overridden": False}
    assert state["quota_purge"] == {"value": False, "default": False, "overridden": False}
    assert state["quota_purge_target_pct"]["value"] == 80

    changed = admin.patch(URL, json={"user_quota_mb": 500, "quota_purge": True})
    assert changed.status_code == 200
    body = changed.json()
    assert body["user_quota_mb"] == {"value": 500, "default": 1024, "overridden": True}
    assert body["quota_purge"]["value"] is True and body["run_retention_days"]["overridden"] is False

    reset = admin.patch(URL, json={"user_quota_mb": None}).json()
    assert reset["user_quota_mb"] == {"value": 1024, "default": 1024, "overridden": False}
    assert reset["quota_purge"]["value"] is True  # lo que no se envía no cambia

    for wrong in ({"user_quota_mb": -1}, {"quota_purge_target_pct": 99}, {"run_retention_days": 4000}, {"x": 1}):
        assert admin.patch(URL, json=wrong).status_code == 422, wrong
    assert user_client.get(URL).status_code == 403
    assert user_client.patch(URL, json={"user_quota_mb": 1}).status_code == 403
    assert TestClient(user_client.app, base_url="https://testserver").get(URL).status_code == 401
    entries = db.scalars(select(AuditEntry).where(AuditEntry.action == "storage.update")).all()
    assert [e.details["changes"] for e in entries][:2] == [
        {"user_quota_mb": {"from": 1024, "to": 500}, "quota_purge": {"from": False, "to": True}},
        {"user_quota_mb": {"from": 500, "to": 1024}},
    ]


def test_invalid_stored_values_are_ignored(
    user_client: TestClient, make_user: Callable[..., User], db: Session
) -> None:
    db.add(AppSetting(key="user_quota_mb", value=-5))
    db.add(AppSetting(key="run_retention_days", value=3))
    db.commit()

    state = _admin(user_client, make_user).get(URL).json()

    assert state["user_quota_mb"] == {"value": 1024, "default": 1024, "overridden": False}
    assert state["run_retention_days"] == {"value": 3, "default": 30, "overridden": True}


def test_env_values_outside_the_web_ranges_do_not_break_anything(
    user_client: TestClient, make_user: Callable[..., User], settings: Settings, db: Session
) -> None:
    """Una variable ``UBW_*`` fuera del rango de la web (p. ej. 5000 días) sigue valiendo; solo las filas se validan."""
    settings.run_retention_days = 5000
    db.add(AppSetting(key="user_quota_mb", value=10))
    db.commit()
    project = new_project(user_client)["id"]

    assert user_client.post(f"/api/v1/projects/{project}/runs", json={"operation": "noop"}).status_code == 202
    state = _admin(user_client, make_user).get(URL).json()
    assert state["run_retention_days"] == {"value": 5000, "default": 5000, "overridden": False}
    assert state["user_quota_mb"]["value"] == 10


# --- cuota global y por usuario ----------------------------------------------------------------------------------


def test_quota_from_admin_setting_and_per_user_without_restart(
    user_client: TestClient, make_user: Callable[..., User], db: Session, user: User
) -> None:
    project = new_project(user_client)["id"]
    _finish(db, launch(user_client, project)["id"], size_mb=2)
    admin = _admin(user_client, make_user)
    runs = f"/api/v1/projects/{project}/runs"

    assert admin.patch(URL, json={"user_quota_mb": 1}).status_code == 200
    blocked = user_client.post(runs, json={"operation": "noop"})
    assert blocked.status_code == 409 and blocked.json()["title"] == "Cuota de almacenamiento superada"

    unlimited = admin.patch(f"/api/v1/users/{user.id}", json={"storage_quota_mb": 0})
    assert unlimited.status_code == 200 and unlimited.json()["storage_quota_mb"] == 0
    assert user_client.post(runs, json={"operation": "noop"}).status_code == 202

    assert admin.patch(f"/api/v1/users/{user.id}", json={"storage_quota_mb": -1}).status_code == 422
    back = admin.patch(f"/api/v1/users/{user.id}", json={"storage_quota_mb": None})
    assert back.status_code == 200 and back.json()["storage_quota_mb"] is None
    assert user_client.post(runs, json={"operation": "noop"}).status_code == 409
    updates = db.scalars(select(AuditEntry).where(AuditEntry.action == "user.update")).all()
    assert [e.details.get("storage_quota_mb") for e in updates] == [0, None]


# --- purga por cuota ---------------------------------------------------------------------------------------------


def test_quota_purge_on_enqueue_frees_the_oldest_unprotected_runs(
    user_client: TestClient, make_user: Callable[..., User], db: Session
) -> None:
    project = new_project(user_client)["id"]
    oldest, cited, recent, old = (launch(user_client, project)["id"] for _ in range(4))
    _finish(db, oldest, ago=timedelta(hours=5))
    _finish(db, cited, ago=timedelta(hours=4))
    _finish(db, recent, ago=timedelta(minutes=10))
    _finish(db, old, ago=timedelta(hours=3))
    active = launch(user_client, project)["id"]
    db.execute(update(Run).where(Run.id == active).values(params={"preview_run": cited}))
    db.commit()
    admin = _admin(user_client, make_user)
    runs = f"/api/v1/projects/{project}/runs"

    admin.patch(URL, json={"user_quota_mb": 3})
    assert user_client.post(runs, json={"operation": "noop"}).status_code == 409  # sin purga: nada se borra
    assert {_status(db, r) for r in (oldest, cited, recent, old)} == {"succeeded"}

    admin.patch(URL, json={"quota_purge": True, "quota_purge_target_pct": 50})
    assert user_client.post(runs, json={"operation": "noop"}).status_code == 202

    statuses = {name: _status(db, r) for name, r in (("oldest", oldest), ("cited", cited), ("recent", recent),
                                                       ("old", old))}  # fmt: skip
    assert statuses == {"oldest": "purged", "cited": "succeeded", "recent": "succeeded", "old": "purged"}
    purges = db.scalars(select(AuditEntry).where(AuditEntry.action == "run.purge")).all()
    assert {p.target_id for p in purges} == {oldest, old}
    assert all(p.actor_user_id is None and (p.details or {}).get("reason") == "quota" for p in purges)


def test_quota_purge_on_upload(user_client: TestClient, make_user: Callable[..., User], db: Session) -> None:
    project = new_project(user_client)["id"]
    run = launch(user_client, project)["id"]
    _finish(db, run, size_mb=1)
    admin = _admin(user_client, make_user)
    admin.patch(URL, json={"user_quota_mb": 1})
    url = f"/api/v1/projects/{project}/uploads"
    csv = {"file": ("datos.csv", b"id;nombre\n1;ana\n")}

    assert user_client.post(url, files=csv).status_code == 409
    admin.patch(URL, json={"quota_purge": True})
    assert user_client.post(url, files=csv).status_code == 201
    assert _status(db, run) == "purged"


def test_preview_matches_what_the_worker_purges(
    user_client: TestClient, make_user: Callable[..., User], db: Session, settings: Settings
) -> None:
    project = new_project(user_client)["id"]
    ancient, old, recent = (launch(user_client, project)["id"] for _ in range(3))
    _finish(db, ancient, ago=timedelta(days=40), size_mb=2)
    _finish(db, old, ago=timedelta(days=2), size_mb=3)
    _finish(db, recent, ago=timedelta(minutes=5), size_mb=1)
    admin = _admin(user_client, make_user)
    proposed = {"run_retention_days": 30, "user_quota_mb": 4, "quota_purge": True}

    preview = admin.post(f"{URL}/preview", json=proposed)
    assert preview.status_code == 200
    assert preview.json() == {"runs": 2, "run_bytes": 5 * MB, "uploads": 0, "upload_bytes": 0, "users": 1}
    assert {_status(db, r) for r in (ancient, old, recent)} == {"succeeded"}  # la vista previa no borra

    admin.patch(URL, json=proposed)
    worker = Worker(settings)
    worker.maintenance(force=True)

    assert [_status(db, r) for r in (ancient, old, recent)] == ["purged", "purged", "succeeded"]


def test_apply_now_is_picked_up_by_the_worker(
    user_client: TestClient, make_user: Callable[..., User], db: Session, settings: Settings
) -> None:
    worker = Worker(settings)
    worker.maintenance(force=True)
    project = new_project(user_client)["id"]
    run = launch(user_client, project)["id"]
    _finish(db, run, ago=timedelta(days=3))
    admin = _admin(user_client, make_user)
    admin.patch(URL, json={"run_retention_days": 1})

    worker.maintenance()  # dentro de la hora: no toca
    assert _status(db, run) == "succeeded"
    assert admin.post(f"{URL}/maintenance").status_code == 202
    worker.maintenance()

    assert _status(db, run) == "purged"
    assert user_client.post(f"{URL}/maintenance").status_code == 403
    assert db.scalars(select(AuditEntry).where(AuditEntry.action == "storage.maintenance")).first() is not None


# --- uso ---------------------------------------------------------------------------------------------------------


def test_usage_by_user_and_my_storage(
    user_client: TestClient, make_user: Callable[..., User], db: Session, user: User
) -> None:
    project = new_project(user_client)["id"]
    _finish(db, launch(user_client, project)["id"], size_mb=256)
    admin = _admin(user_client, make_user)

    page = admin.get(f"{URL}/usage", params={"limit": 1}).json()
    assert page["total"] == 2 and len(page["items"]) == 1
    mine = page["items"][0]
    assert (mine["username"], mine["used_bytes"], mine["quota_bytes"], mine["quota_source"], mine["used_pct"]) == (
        user.username, 256 * MB, 1024 * MB, "global", 25.0
    )  # fmt: skip
    assert admin.get(f"{URL}/usage", params={"q": "roo"}).json()["items"][0]["username"] == "root"
    assert user_client.get(f"{URL}/usage").status_code == 403

    own = user_client.get("/api/v1/auth/me/storage").json()
    assert own == {
        "run_bytes": 256 * MB, "upload_bytes": 0, "used_bytes": 256 * MB, "quota_bytes": 1024 * MB,
        "quota_source": "global", "used_pct": 25.0, "quota_purge": False, "quota_purge_target_pct": 80,
    }  # fmt: skip
    admin.patch(f"/api/v1/users/{user.id}", json={"storage_quota_mb": 0})
    unlimited = user_client.get("/api/v1/auth/me/storage").json()
    assert (unlimited["quota_bytes"], unlimited["quota_source"], unlimited["used_pct"]) == (None, "unlimited", None)
    assert admin.get("/api/v1/auth/me/storage").json()["used_bytes"] == 0  # cada uno ve solo lo suyo
    assert TestClient(user_client.app, base_url="https://testserver").get("/api/v1/auth/me/storage").status_code == 401
