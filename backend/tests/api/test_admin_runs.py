"""Ejecuciones desde administración: lista de todos los proyectos (solo metadatos) y borrado completo, por ejecución y
por proyecto (sesión ``2026-11-06-explorer-runs-lists``, D1-D3, D7, D8)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, Run, User
from app.domain.runs import admin as admin_domain
from app.jobs.worker import Worker
from app.workspace.layout import run_dir
from tests.api.test_projects import login_as
from tests.api.test_runs import launch, project, wait_for, worker  # noqa: F401  (fixtures)

LIST = "/api/v1/admin/runs"


@pytest.fixture
def boss(user_client: TestClient, make_user: Callable[..., User]) -> TestClient:
    """Administrador que **no** es miembro del proyecto del usuario."""
    return login_as(user_client, make_user, "jefa", role="admin")


def _finished(client: TestClient, worker: Worker, db: Session, project_id: object) -> Run:  # noqa: F811
    run = wait_for(worker, db, str(launch(client, project_id, steps=1, step_seconds=0)["id"]))
    assert run.status == "succeeded", (run.error_code, run.error_message)
    return run


def test_list_shows_every_project_without_content(
    user_client: TestClient,
    boss: TestClient,
    project: dict[str, object],  # noqa: F811
    worker: Worker,  # noqa: F811
    db: Session,
) -> None:
    done = _finished(user_client, worker, db, project["id"])
    queued = launch(user_client, project["id"], steps=1, step_seconds=0)

    assert user_client.get(LIST).status_code == 403
    body = boss.get(LIST).json()
    assert body["total"] == 2
    row = next(r for r in body["items"] if r["id"] == done.id)
    assert row["project_name"] == project["name"] and row["username"] == "ana" and row["artifacts_count"] > 0
    assert set(row) == {
        "id", "project_id", "project_name", "operation", "status", "username", "created_at", "finished_at",
        "size_bytes", "artifacts_count",
    }  # fmt: skip
    # El admin no miembro sigue sin ver el contenido por la API normal.
    assert boss.get(f"/api/v1/runs/{done.id}").status_code == 404

    by_size = boss.get(LIST, params={"sort": "size", "order": "asc"}).json()["items"]
    assert [r["id"] for r in by_size] == [str(queued["id"]), done.id]
    assert boss.get(LIST, params={"q": str(project["name"])[:5]}).json()["total"] == 2
    assert boss.get(LIST, params={"status": "queued"}).json()["items"][0]["id"] == queued["id"]
    assert boss.get(LIST, params={"q": "nada-coincide_%"}).json()["total"] == 0
    assert boss.get(LIST, params={"sort": "params"}).status_code == 422


def test_delete_one_run_removes_row_files_and_keeps_audit(
    user_client: TestClient,
    boss: TestClient,
    project: dict[str, object],  # noqa: F811
    worker: Worker,  # noqa: F811
    db: Session,
    settings: Settings,
) -> None:
    run = _finished(user_client, worker, db, project["id"])
    run_id = run.id
    folder = run_dir(settings.workspace_dir, str(run.workspace_path))
    assert folder.is_dir()
    relaunched = user_client.post(f"/api/v1/runs/{run_id}/relaunch").json()
    assert user_client.get(f"/api/v1/runs/{relaunched['id']}").json()["relaunched_from_exists"] is True

    assert user_client.delete(f"{LIST}/{run_id}").status_code == 403
    assert boss.delete(f"{LIST}/{relaunched['id']}").status_code == 409  # en cola
    assert boss.delete(f"{LIST}/{run_id}").status_code == 204

    db.expunge_all()
    assert db.get(Run, run_id) is None and not folder.exists()
    assert user_client.get(f"/api/v1/runs/{run_id}").status_code == 404
    # «Relanzada desde» se muestra sin enlace (D7).
    assert user_client.get(f"/api/v1/runs/{relaunched['id']}").json()["relaunched_from_exists"] is False
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "run.delete")).one()
    assert entry.target_id == run_id and "params" not in (entry.details or {})
    assert boss.delete(f"{LIST}/{run_id}").status_code == 404


def test_delete_keeps_going_if_the_folder_cannot_be_removed(
    user_client: TestClient,
    boss: TestClient,
    project: dict[str, object],  # noqa: F811
    worker: Worker,  # noqa: F811
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    run_id = _finished(user_client, worker, db, project["id"]).id

    def broken(_: Path) -> None:
        raise OSError("ocupado")

    monkeypatch.setattr(admin_domain, "remove_tree", broken)

    assert boss.delete(f"{LIST}/{run_id}").status_code == 204
    db.expunge_all()
    assert db.get(Run, run_id) is None  # la fila se borra; la carpeta queda huérfana con un aviso en el log
    assert "No se pudo borrar la carpeta" in caplog.text


def test_delete_project_runs_confirms_skips_and_reports(
    user_client: TestClient,
    boss: TestClient,
    project: dict[str, object],  # noqa: F811
    worker: Worker,  # noqa: F811
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _finished(user_client, worker, db, project["id"])
    second = _finished(user_client, worker, db, project["id"])
    pending = _finished(user_client, worker, db, project["id"])
    queued = launch(user_client, project["id"], steps=1, step_seconds=0)
    sizes = first.size_bytes + second.size_bytes
    pending_id, pending_size = pending.id, pending.size_bytes
    original = admin_domain.dump_journal
    monkeypatch.setattr(
        admin_domain, "dump_journal", lambda run, s: Path("diario") if run.id == pending_id else original(run, s)
    )
    url = f"/api/v1/admin/projects/{project['id']}/runs"

    summary = boss.get(f"{url}/summary").json()
    assert (summary["project_name"], summary["runs"]) == (project["name"], 4)
    assert summary["size_bytes"] == sizes + pending_size
    assert user_client.post(f"{url}/delete", json={"confirm": project["name"]}).status_code == 403
    assert boss.post(f"{url}/delete", json={"confirm": "otro nombre"}).status_code == 422
    assert boss.post("/api/v1/admin/projects/999/runs/delete", json={"confirm": "x"}).status_code == 404
    assert boss.delete(f"{LIST}/{pending_id}").status_code == 409  # volcado con constraints pendientes (G31)

    result = boss.post(f"{url}/delete", json={"confirm": project["name"]}).json()

    assert result == {
        "deleted": 2,
        "skipped_active": 1,
        "skipped_pending_dump": 1,
        "freed_bytes": sizes,
    }
    db.expunge_all()
    left = {r.id for r in db.scalars(select(Run).where(Run.project_id == project["id"]))}
    assert left == {pending_id, str(queued["id"])}
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "project.runs_delete")).one()
    assert entry.details is not None and entry.details["deleted"] == 2
