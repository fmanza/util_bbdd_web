"""Transferencia de proyectos y conexiones entre usuarios (ADR-013, entrega B): carpetas, rutas, bloqueos,
vuelta atrás y recuperación de diarios."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, Connection, DocumentTemplate, Project, ProjectMember, Run, Upload, User
from app.domain.identity import transfer
from app.domain.identity.audit import CLI_CONTEXT
from app.domain.identity.errors import TransferBlockedError
from app.jobs.worker import Worker
from tests.api.test_bulk import INSERT_CSV
from tests.api.test_bulk import upload as upload_csv
from tests.api.test_connections import PG
from tests.api.test_projects import login_as, new_project
from tests.api.test_runs import launch, wait_for, worker  # noqa: F401 (fixture)
from tests.api.test_templates import project_url
from tests.api.test_templates import upload as upload_template
from tests.unit.test_templates_units import word_template


def _id(db: Session, username: str) -> int:
    return db.scalars(select(User.id).where(User.username == username)).one()


def _folder(settings: Settings, owner_id: int, project_id: object) -> Path:
    return Path(settings.workspace_dir) / "users" / str(owner_id) / "projects" / str(project_id)


def test_transfer_moves_folders_paths_ownership_and_allows_deletion(
    admin_client: TestClient,
    make_user: Callable[..., User],
    db: Session,
    settings: Settings,
    worker: Worker,  # noqa: F811
) -> None:
    luis = login_as(admin_client, make_user, "luis")
    mar = login_as(admin_client, make_user, "mar")
    project = new_project(luis, "Ventas")
    new_project(mar, "ventas")  # mismo nombre en el destino: se renombra
    others = new_project(mar, "De Mar")
    mar.post(f"/api/v1/projects/{others['id']}/members", json={"username": "luis", "role": "viewer"})
    connection_id = luis.post("/api/v1/connections", json=PG).json()["id"]
    luis.post(f"/api/v1/projects/{project['id']}/connections", json={"connection_id": connection_id, "alias": "o"})
    unused_id = luis.post("/api/v1/connections", json={**PG, "name": "Sin uso"}).json()["id"]
    run_id = str(launch(luis, project["id"], steps=1, step_seconds=0)["id"])
    wait_for(worker, db, run_id)
    upload_id = upload_csv(luis, project["id"], "c.csv", INSERT_CSV).json()["id"]
    template = upload_template(luis, project_url(project["id"]), "Corp.docx", word_template(), name="Corp").json()
    luis_id, mar_id = _id(db, "luis"), _id(db, "mar")
    assert _folder(settings, luis_id, project["id"]).is_dir()

    preview = admin_client.get(f"/api/v1/users/{luis_id}/transfer-preview", params={"target_user_id": mar_id})
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["can_transfer"] is True and body["reasons"] == []
    assert [(p["id"], p["name"], p["new_name"]) for p in body["created_projects"]] == [
        (project["id"], "Ventas", "Ventas (de luis)")
    ]
    assert [p["id"] for p in body["owned_projects"]] == [project["id"]]
    assert [(p["id"], p["role"]) for p in body["other_memberships"]] == [(others["id"], "viewer")]
    assert [c["id"] for c in body["connections"]] == [connection_id]  # la privada sin uso no se cede

    done = admin_client.post(
        f"/api/v1/users/{luis_id}/transfer", json={"target_user_id": mar_id, "remove_memberships": True}
    )

    assert done.status_code == 200, done.text
    assert not (Path(settings.workspace_dir) / transfer.JOURNAL_DIR).exists() or not any(
        (Path(settings.workspace_dir) / transfer.JOURNAL_DIR).iterdir()
    )
    assert not _folder(settings, luis_id, project["id"]).exists()
    assert _folder(settings, mar_id, project["id"]).is_dir()
    db.expire_all()
    moved = db.get(Project, project["id"])
    assert moved is not None and (moved.owner_id, moved.name) == (mar_id, "Ventas (de luis)")
    prefix = f"users/{mar_id}/projects/{project['id']}/"
    assert str(db.get(Run, run_id).workspace_path).startswith(prefix)  # type: ignore[union-attr]
    assert str(db.get(Upload, upload_id).path).startswith(prefix)  # type: ignore[union-attr]
    assert str(db.get(DocumentTemplate, template["id"]).path).startswith(prefix)  # type: ignore[union-attr]
    assert db.get(ProjectMember, (project["id"], mar_id)).role == "owner"  # type: ignore[union-attr]
    assert db.scalars(select(ProjectMember).where(ProjectMember.user_id == luis_id)).all() == []
    assert db.get(Connection, connection_id).owner_id == mar_id  # type: ignore[union-attr]
    assert db.get(Connection, unused_id).owner_id == luis_id  # type: ignore[union-attr]
    # Todo sigue accesible desde la carpeta nueva.
    artifacts = mar.get(f"/api/v1/runs/{run_id}").json()["artifacts"]
    assert mar.get(f"/api/v1/runs/{run_id}/artifacts/{artifacts[0]['id']}").status_code == 200
    assert mar.get(f"/api/v1/projects/{project['id']}/uploads/{upload_id}/info").status_code == 200
    assert mar.get(f"{project_url(project['id'])}/{template['id']}/file").status_code == 200
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "user.transfer")).one()
    assert entry.details is not None
    assert entry.details["renamed"] == {f"project:{project['id']}": "Ventas (de luis)"}
    assert set(entry.details["removed_memberships"]) == {project["id"], others["id"]}

    assert admin_client.get(f"/api/v1/users/{luis_id}/deletion-check").json()["can_delete"] is True
    assert admin_client.delete(f"/api/v1/users/{luis_id}").status_code == 204


def test_transfer_keeps_memberships_unless_asked(
    admin_client: TestClient, make_user: Callable[..., User], db: Session
) -> None:
    luis = login_as(admin_client, make_user, "luis")
    make_user("mar")
    project = new_project(luis, "Uno")
    luis_id, mar_id = _id(db, "luis"), _id(db, "mar")

    response = admin_client.post(f"/api/v1/users/{luis_id}/transfer", json={"target_user_id": mar_id})

    assert response.status_code == 200
    db.expire_all()
    roles = {
        m.user_id: m.role for m in db.scalars(select(ProjectMember).where(ProjectMember.project_id == project["id"]))
    }
    assert roles == {luis_id: "owner", mar_id: "owner"}
    assert admin_client.get(f"/api/v1/users/{luis_id}/deletion-check").json()["reasons"] == ["member"]


def test_name_clashes_never_collide_among_themselves() -> None:
    rows = [(1, "A"), (2, "A (de luis)"), (3, "b")]

    renamed = transfer._renamed(rows, {"a", "a (de luis)"}, " (de luis)")

    assert renamed == [(1, "A", "A (de luis) 2"), (2, "A (de luis)", "A (de luis) (de luis)"), (3, "b", None)]
    long = transfer._renamed([(1, "x" * 100)], {"x" * 100}, " (de luis)")[0][2]
    assert long is not None and len(long) == 100 and long.endswith(" (de luis)")


def test_transfer_reasons(admin_client: TestClient, admin: User, make_user: Callable[..., User], db: Session) -> None:
    luis = login_as(admin_client, make_user, "luis")
    busy = new_project(luis, "Ocupado")
    launch(luis, busy["id"], steps=1)  # en cola, sin worker
    inactive = make_user("ina")
    inactive.is_active = False
    db.commit()
    admin_client.post("/api/v1/connections", json={**PG, "name": "Común", "visibility": "shared"})
    luis_id = _id(db, "luis")
    mar = make_user("mar")

    def reasons(origin: int, target: int) -> list[str]:
        response = admin_client.get(f"/api/v1/users/{origin}/transfer-preview", params={"target_user_id": target})
        assert response.status_code == 200, response.text
        result: list[str] = response.json()["reasons"]
        return result

    assert reasons(luis_id, luis_id) == ["same_user", "busy"]
    same = admin_client.get(f"/api/v1/users/{luis_id}/transfer-preview", params={"target_user_id": luis_id}).json()
    assert [p["new_name"] for p in same["created_projects"]] == [None]  # sin renombrados absurdos
    assert reasons(luis_id, inactive.id) == ["target_inactive", "busy"]
    assert reasons(admin.id, mar.id) == ["target_cannot_share"]  # la compartida solo va a otro admin
    blocked = admin_client.post(f"/api/v1/users/{luis_id}/transfer", json={"target_user_id": mar.id})
    assert blocked.status_code == 409
    assert [(p["id"], p["name"]) for p in blocked.json()["busy_projects"]] == [(busy["id"], "Ocupado")]
    assert "pg-secreta" not in blocked.text
    db.expire_all()
    assert db.get(Project, busy["id"]).owner_id == luis_id  # type: ignore[union-attr]
    assert admin_client.post(f"/api/v1/users/{luis_id}/transfer", json={"target_user_id": 9999}).status_code == 404


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/api/v1/users/1/transfer-preview?target_user_id=2"), ("POST", "/api/v1/users/1/transfer")],
)
def test_transfer_is_admin_only(user_client: TestClient, method: str, path: str) -> None:
    assert user_client.request(method, path, json={"target_user_id": 2}).status_code == 403


def test_transfer_requires_csrf(admin_client: TestClient, user: User, admin: User) -> None:
    del admin_client.headers["X-CSRF-Token"]

    assert admin_client.post(f"/api/v1/users/{user.id}/transfer", json={"target_user_id": admin.id}).status_code == 403


# --- vuelta atrás y diarios ----------------------------------------------------------------------------------------


def _two_projects(db: Session, make_user: Callable[..., User], settings: Settings) -> tuple[User, User, list[Project]]:
    luis, mar = make_user("luis"), make_user("mar")
    projects = [Project(owner_id=luis.id, name=name) for name in ("P1", "P2")]
    db.add_all(projects)
    db.flush()
    db.add_all([ProjectMember(project_id=p.id, user_id=luis.id, role="owner") for p in projects])
    db.commit()
    for p in projects:
        folder = _folder(settings, luis.id, p.id)
        folder.mkdir(parents=True)
        (folder / "dato.txt").write_text("x", encoding="utf-8")
    return luis, mar, projects


def test_failed_move_restores_folders_and_database(
    db: Session, make_user: Callable[..., User], settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    luis, mar, projects = _two_projects(db, make_user, settings)
    real = transfer._move
    calls: list[Any] = []

    def flaky(s: Settings, source: str, destination: str) -> bool:
        calls.append(source)
        if len(calls) == 2:
            raise OSError("disco lleno")
        return real(s, source, destination)

    monkeypatch.setattr(transfer, "_move", flaky)

    with pytest.raises(OSError, match="disco lleno"):
        transfer.transfer_user(db, luis, mar, actor=luis, remove_memberships=False, settings=settings, ctx=CLI_CONTEXT)

    db.expire_all()
    for p in projects:
        assert db.get(Project, p.id).owner_id == luis.id  # type: ignore[union-attr]
        assert (_folder(settings, luis.id, p.id) / "dato.txt").is_file()
        assert not _folder(settings, mar.id, p.id).exists()
    assert list((Path(settings.workspace_dir) / transfer.JOURNAL_DIR).glob("*.json")) == []


def test_failed_commit_restores_folders(
    db: Session, make_user: Callable[..., User], settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    luis, mar, projects = _two_projects(db, make_user, settings)

    def broken() -> None:
        raise RuntimeError("commit roto")

    monkeypatch.setattr(db, "commit", broken)

    with pytest.raises(RuntimeError, match="commit roto"):
        transfer.transfer_user(db, luis, mar, actor=luis, remove_memberships=False, settings=settings, ctx=CLI_CONTEXT)

    monkeypatch.undo()
    db.expire_all()
    for p in projects:
        assert db.get(Project, p.id).owner_id == luis.id  # type: ignore[union-attr]
        assert (_folder(settings, luis.id, p.id) / "dato.txt").is_file()


@pytest.mark.parametrize("committed", [True, False])
def test_recover_interrupted_transfer(
    db: Session, make_user: Callable[..., User], settings: Settings, committed: bool
) -> None:
    """El proceso murió entre mover y confirmar: según la BD, se terminan los movimientos o se deshacen."""
    luis, mar, projects = _two_projects(db, make_user, settings)
    p1, p2 = projects
    if committed:  # la BD ya tiene al destino; solo P1 llegó a moverse
        db.execute(update(Project).values(owner_id=mar.id))
        db.commit()
        _folder(settings, mar.id, p1.id).parent.mkdir(parents=True)
        _folder(settings, luis.id, p1.id).rename(_folder(settings, mar.id, p1.id))
    else:  # la BD no se confirmó, pero P1 ya se había movido
        _folder(settings, mar.id, p1.id).parent.mkdir(parents=True)
        _folder(settings, luis.id, p1.id).rename(_folder(settings, mar.id, p1.id))
    moves = [
        {"project_id": p.id, "from": f"users/{luis.id}/projects/{p.id}", "to": f"users/{mar.id}/projects/{p.id}"}
        for p in (p1, p2)
    ]
    journal = Path(settings.workspace_dir) / transfer.JOURNAL_DIR / "01J.json"
    journal.parent.mkdir(parents=True)
    journal.write_text(json.dumps({"origin": luis.id, "target": mar.id, "moves": moves}), encoding="utf-8")

    assert transfer.recover_transfers(db, settings) == 1

    owner = mar if committed else luis
    for p in (p1, p2):
        assert (_folder(settings, owner.id, p.id) / "dato.txt").is_file()
    assert not journal.exists()


def test_worker_start_recovers_journals(settings: Settings, migrated: Settings) -> None:
    folder = Path(settings.workspace_dir) / transfer.JOURNAL_DIR
    folder.mkdir(parents=True)
    (folder / "vacio.json").write_text(json.dumps({"origin": 1, "target": 2, "moves": []}), encoding="utf-8")
    w = Worker(settings.model_copy(update={"worker_poll_seconds": 0.2}))

    w.start()
    try:
        assert not (folder / "vacio.json").exists()
    finally:
        w.shutdown()


def test_file_written_during_a_transfer_is_relocated(
    db: Session, make_user: Callable[..., User], settings: Settings
) -> None:
    luis, mar, projects = _two_projects(db, make_user, settings)
    project = projects[0]
    stale_owner = project.owner_id
    written = _folder(settings, luis.id, project.id) / "uploads" / "f.csv"
    written.parent.mkdir()
    written.write_text("a;b\n", encoding="utf-8")
    # Otra sesión transfiere el proyecto mientras se escribía el fichero.
    db.execute(
        update(Project)
        .where(Project.id == project.id)
        .values(owner_id=mar.id)
        .execution_options(synchronize_session=False)
    )

    moved = transfer.relocate_if_transferred(db, settings, project, written.resolve())

    assert stale_owner == luis.id
    assert moved == (_folder(settings, mar.id, project.id) / "uploads" / "f.csv").resolve()
    assert moved.is_file() and not written.exists()
    assert project.owner_id == mar.id
    assert transfer.relocate_if_transferred(db, settings, project, moved) == moved  # sin cambios: se queda


def test_transfer_without_folders_only_updates_the_database(
    db: Session, make_user: Callable[..., User], settings: Settings
) -> None:
    luis, mar = make_user("luis"), make_user("mar")
    project = Project(owner_id=luis.id, name="Vacío")
    db.add(project)
    db.commit()

    plan = transfer.transfer_user(
        db, luis, mar, actor=luis, remove_memberships=False, settings=settings, ctx=CLI_CONTEXT
    )

    assert [p.id for p in plan.created_projects] == [project.id]
    db.expire_all()
    assert db.get(Project, project.id).owner_id == mar.id  # type: ignore[union-attr]
    with pytest.raises(TransferBlockedError):
        transfer.transfer_user(db, mar, mar, actor=luis, remove_memberships=False, settings=settings, ctx=CLI_CONTEXT)
