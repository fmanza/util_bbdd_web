"""Motor de ejecuciones de extremo a extremo con subprocesos reales (sin servicios externos, apto para el CI).

API (encolar, historial, cancelar, relanzar, purgar, artefactos, ZIP, SSE) + ``Worker`` (éxito, fallo,
cancelación en curso, timeout, hijo muerto, huérfanos, retención y conexión SQLite real).
"""

from __future__ import annotations

import io
import json
import sqlite3
import time
import zipfile
from collections.abc import Callable, Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import TERMINAL_STATUSES, Artifact, Run, User, utcnow
from app.domain.runs.service import apply_retention
from app.jobs.worker import Worker
from app.workspace.layout import run_dir
from tests.api.test_projects import login_as, new_project

SECRET = "sqlite-no-tiene-pero-por-si-acaso"


@pytest.fixture
def worker(settings: Settings, migrated: Settings) -> Iterator[Worker]:
    w = Worker(settings.model_copy(update={"worker_poll_seconds": 0.2}))
    w.start()
    yield w
    w.shutdown()


def wait_for(
    worker: Worker, db: Session, run_id: str, *, statuses: frozenset[str] = TERMINAL_STATUSES, timeout: float = 90
) -> Run:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        worker.tick()
        db.expire_all()
        run = db.get(Run, run_id)
        assert run is not None
        if run.status in statuses:
            return run
        time.sleep(0.2)
    raise AssertionError(f"La ejecución {run_id} no llegó a {sorted(statuses)}")


@pytest.fixture
def project(user_client: TestClient) -> dict[str, object]:
    return new_project(user_client)


def launch(client: TestClient, project_id: object, **params: object) -> dict[str, object]:
    response = client.post(f"/api/v1/projects/{project_id}/runs", json={"operation": "noop", "params": params})
    assert response.status_code == 202, response.text
    body: dict[str, object] = response.json()
    return body


# --- encolar y estados -------------------------------------------------------------------------------------------


def test_enqueue_validates_and_returns_202(user_client: TestClient, project: dict[str, object]) -> None:
    run = launch(user_client, project["id"], steps=2)

    assert run["status"] == "queued"
    assert len(str(run["id"])) == 26
    assert run["params"] == {"steps": 2, "step_seconds": 1.0, "fail": False, "connection": None}
    base = f"/api/v1/projects/{project['id']}/runs"
    assert user_client.post(base, json={"operation": "borrar_todo"}).status_code == 422
    bad = user_client.post(base, json={"operation": "noop", "params": {"steps": 0}})
    assert bad.status_code == 422
    assert bad.json()["errors"][0]["loc"] == ["body", "params", "steps"]
    unknown_alias = user_client.post(base, json={"operation": "noop", "params": {"connection": "origen"}})
    assert unknown_alias.status_code == 422


def test_queue_limit_and_quota(
    user_client: TestClient,
    project: dict[str, object],
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    db: Session,
) -> None:
    monkeypatch.setattr(settings, "max_queued_per_user", 2)
    launch(user_client, project["id"])
    launch(user_client, project["id"])
    assert user_client.post(f"/api/v1/projects/{project['id']}/runs", json={"operation": "noop"}).status_code == 429

    db.execute(update(Run).values(status="succeeded", size_bytes=2 * 1024 * 1024))
    db.commit()
    monkeypatch.setattr(settings, "user_quota_mb", 1)
    assert user_client.post(f"/api/v1/projects/{project['id']}/runs", json={"operation": "noop"}).status_code == 409


def test_cancel_queued_run_is_immediate(user_client: TestClient, project: dict[str, object]) -> None:
    run = launch(user_client, project["id"])

    cancelled = user_client.post(f"/api/v1/runs/{run['id']}/cancel")

    assert cancelled.status_code == 202
    assert cancelled.json()["status"] == "cancelled"
    assert user_client.post(f"/api/v1/runs/{run['id']}/cancel").status_code == 409


def test_history_filters_and_my_runs(user_client: TestClient, project: dict[str, object]) -> None:
    first = launch(user_client, project["id"])
    launch(user_client, project["id"])
    user_client.post(f"/api/v1/runs/{first['id']}/cancel")

    history = user_client.get(f"/api/v1/projects/{project['id']}/runs").json()
    cancelled = user_client.get(f"/api/v1/projects/{project['id']}/runs", params={"status": "cancelled"}).json()
    searched = user_client.get(f"/api/v1/projects/{project['id']}/runs", params={"q": str(first["id"])[-8:]}).json()

    assert history["total"] == 2
    assert history["items"][0]["created_at"] >= history["items"][1]["created_at"]
    assert [r["id"] for r in cancelled["items"]] == [first["id"]]
    assert [r["id"] for r in searched["items"]] == [first["id"]]
    assert user_client.get("/api/v1/runs").json()["total"] == 2


def test_run_of_other_project_is_404(
    user_client: TestClient, project: dict[str, object], make_user: Callable[..., User]
) -> None:
    run = launch(user_client, project["id"])
    outsider = login_as(user_client, make_user, "luis")

    for method, path in [
        ("GET", f"/api/v1/runs/{run['id']}"),
        ("GET", f"/api/v1/runs/{run['id']}/events"),
        ("POST", f"/api/v1/runs/{run['id']}/cancel"),
        ("POST", f"/api/v1/runs/{run['id']}/relaunch"),
        ("DELETE", f"/api/v1/runs/{run['id']}"),
        ("GET", f"/api/v1/runs/{run['id']}/archive"),
        ("GET", f"/api/v1/runs/{run['id']}/artifacts/1"),
    ]:
        assert outsider.request(method, path).status_code == 404, path
    assert outsider.get("/api/v1/runs").json()["total"] == 0


def test_viewer_can_read_but_not_cancel(
    user_client: TestClient, project: dict[str, object], make_user: Callable[..., User]
) -> None:
    run = launch(user_client, project["id"])
    viewer = login_as(user_client, make_user, "vera")
    user_client.post(f"/api/v1/projects/{project['id']}/members", json={"username": "vera"})

    assert viewer.get(f"/api/v1/runs/{run['id']}").json()["my_role"] == "viewer"
    assert viewer.post(f"/api/v1/runs/{run['id']}/cancel").status_code == 403
    assert viewer.post(f"/api/v1/runs/{run['id']}/relaunch").status_code == 403


# --- worker con subprocesos reales -------------------------------------------------------------------------------


def test_noop_succeeds_with_artifacts_manifest_and_log(
    user_client: TestClient, project: dict[str, object], worker: Worker, db: Session, settings: Settings
) -> None:
    run_id = str(launch(user_client, project["id"], steps=3, step_seconds=0)["id"])

    run = wait_for(worker, db, run_id)

    assert run.status == "succeeded", (run.error_code, run.error_message)
    assert (run.phase, run.progress_pct) == ("done", 100)
    directory = run_dir(settings.workspace_dir, str(run.workspace_path))
    assert directory.name.endswith(f"_noop_{run_id}")
    manifest = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "succeeded"
    assert manifest["versions"]["util_bbdd"] == "4.4.0"
    assert {a["path"] for a in manifest["artifacts"]} >= {"outputs/markdown/resumen.md", "outputs/graphs/pasos.svg"}
    log = (directory / "logs" / "run.log").read_text(encoding="utf-8")
    assert "Ejecución terminada" in log
    detail = user_client.get(f"/api/v1/runs/{run_id}").json()
    kinds = {a["kind"]: a for a in detail["artifacts"]}
    assert set(kinds) >= {"html", "markdown", "sql", "graphs", "log", "manifest"}
    assert kinds["html"]["previewable"] is True
    assert detail["duration_seconds"] is not None and detail["size_bytes"] > 0


def test_artifact_download_preview_and_archive(
    user_client: TestClient, project: dict[str, object], worker: Worker, db: Session
) -> None:
    run_id = str(launch(user_client, project["id"], steps=1, step_seconds=0)["id"])
    wait_for(worker, db, run_id)
    artifacts = {a["kind"]: a for a in user_client.get(f"/api/v1/runs/{run_id}").json()["artifacts"]}

    html = user_client.get(f"/api/v1/runs/{run_id}/artifacts/{artifacts['html']['id']}/preview")
    download = user_client.get(f"/api/v1/runs/{run_id}/artifacts/{artifacts['html']['id']}")
    sql = user_client.get(f"/api/v1/runs/{run_id}/artifacts/{artifacts['sql']['id']}/preview")
    archive = user_client.get(f"/api/v1/runs/{run_id}/archive")

    assert html.status_code == 200
    assert html.headers["content-security-policy"].startswith("sandbox")
    assert html.headers["x-content-type-options"] == "nosniff"
    assert "inline" in html.headers["content-disposition"]
    assert download.headers["content-disposition"].startswith("attachment")
    assert sql.headers["content-type"].startswith("text/plain")
    assert "SELECT 1" in sql.text
    with zipfile.ZipFile(io.BytesIO(archive.content)) as zipped:
        names = zipped.namelist()
    assert any(name.endswith("/run.json") for name in names)
    assert any(name.endswith("/outputs/html/resumen.html") for name in names)
    assert archive.headers["content-disposition"].startswith("attachment")


def test_tampered_artifact_path_is_404(
    user_client: TestClient, project: dict[str, object], worker: Worker, db: Session
) -> None:
    run_id = str(launch(user_client, project["id"], steps=1, step_seconds=0)["id"])
    wait_for(worker, db, run_id)
    artifact = db.scalars(select(Artifact).where(Artifact.run_id == run_id)).first()
    assert artifact is not None
    artifact.path = "../../../../../data/config.db"
    db.commit()

    assert user_client.get(f"/api/v1/runs/{run_id}/artifacts/{artifact.id}").status_code == 404
    assert user_client.get(f"/api/v1/runs/{run_id}/artifacts/999999").status_code == 404


def test_sse_streams_snapshots_until_end(
    user_client: TestClient, project: dict[str, object], worker: Worker, db: Session
) -> None:
    run_id = str(launch(user_client, project["id"], steps=1, step_seconds=0)["id"])
    wait_for(worker, db, run_id)

    with user_client.stream("GET", f"/api/v1/runs/{run_id}/events") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())

    events = [line.removeprefix("event: ") for line in body.splitlines() if line.startswith("event: ")]
    assert events == ["run", "end"]
    data = json.loads(next(line for line in body.splitlines() if line.startswith("data: "))[6:])
    assert data["status"] == "succeeded"


def test_failing_job_records_error(
    user_client: TestClient, project: dict[str, object], worker: Worker, db: Session
) -> None:
    run_id = str(launch(user_client, project["id"], steps=1, step_seconds=0, fail=True)["id"])

    run = wait_for(worker, db, run_id)

    assert (run.status, run.error_code) == ("failed", "noop_failed")
    assert run.manifest is not None and run.manifest["status"] == "failed"


def test_cancel_running_job_terminates_subprocess(
    user_client: TestClient, project: dict[str, object], worker: Worker, db: Session
) -> None:
    run_id = str(launch(user_client, project["id"], steps=10, step_seconds=3)["id"])
    wait_for(worker, db, run_id, statuses=frozenset({"running"}))
    process = worker.children[run_id].process

    assert user_client.post(f"/api/v1/runs/{run_id}/cancel").json()["cancel_requested"] is True
    run = wait_for(worker, db, run_id)

    assert (run.status, run.error_code) == ("cancelled", "cancelled")
    assert not process.is_alive()


def test_job_timeout_and_crashed_child(
    user_client: TestClient, project: dict[str, object], worker: Worker, db: Session, settings: Settings
) -> None:
    worker.settings = worker.settings.model_copy(update={"job_timeout_seconds": 1})
    slow = str(launch(user_client, project["id"], steps=10, step_seconds=3)["id"])
    assert wait_for(worker, db, slow).error_code == "job_timeout"

    worker.settings = worker.settings.model_copy(update={"job_timeout_seconds": 3600})
    crashing = str(launch(user_client, project["id"], steps=10, step_seconds=3)["id"])
    wait_for(worker, db, crashing, statuses=frozenset({"running"}))
    worker.children[crashing].process.kill()
    run = wait_for(worker, db, crashing)

    assert (run.status, run.error_code) == ("failed", "worker_crash")


def test_orphans_from_previous_worker_are_closed(
    user_client: TestClient, project: dict[str, object], db: Session, settings: Settings
) -> None:
    run_id = str(launch(user_client, project["id"])["id"])
    db.execute(
        update(Run)
        .where(Run.id == run_id)
        .values(status="running", worker_id="antiguo", heartbeat_at=utcnow() - timedelta(minutes=10))
    )
    db.commit()

    Worker(settings).recover_orphans()

    db.expire_all()
    run = db.get(Run, run_id)
    assert run is not None and (run.status, run.error_code) == ("failed", "interrupted")


def test_noop_with_real_sqlite_connection_and_no_secrets(
    user_client: TestClient, project: dict[str, object], worker: Worker, db: Session, settings: Settings
) -> None:
    con = sqlite3.connect(settings.files_dir / "demo.db")
    con.execute("CREATE TABLE t (id INTEGER)")
    con.close()
    connection_id = user_client.post(
        "/api/v1/connections", json={"name": "Demo", "db_type": "sqlite", "params": {"database": "demo.db"}}
    ).json()["id"]
    user_client.post(
        f"/api/v1/projects/{project['id']}/connections", json={"connection_id": connection_id, "alias": "origen"}
    )

    run_id = str(launch(user_client, project["id"], steps=1, step_seconds=0, connection="origen")["id"])
    run = wait_for(worker, db, run_id)

    assert run.status == "succeeded", (run.error_code, run.error_message)
    directory = run_dir(settings.workspace_dir, str(run.workspace_path))
    summary = (directory / "outputs" / "markdown" / "resumen.md").read_text(encoding="utf-8")
    assert "sqlite" in summary
    manifest = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    assert manifest["connections"] == [
        {"alias": "origen", "connection_id": connection_id, "name": "Demo", "db_type": "sqlite"}
    ]


def test_noop_with_postgres_connection_never_writes_the_secret(
    user_client: TestClient, project: dict[str, object], worker: Worker, db: Session, settings: Settings
) -> None:
    connection_id = user_client.post(
        "/api/v1/connections",
        json={
            "name": "PG",
            "db_type": "postgresql",
            "params": {"host": "10.9.9.9", "user": "u", "database": "d"},
            "password": SECRET,
        },
    ).json()["id"]
    user_client.post(
        f"/api/v1/projects/{project['id']}/connections", json={"connection_id": connection_id, "alias": "pg"}
    )

    run = wait_for(worker, db, str(launch(user_client, project["id"], steps=1, step_seconds=0, connection="pg")["id"]))

    assert (run.status, run.error_code) == ("failed", "not_allowed")
    directory = run_dir(settings.workspace_dir, str(run.workspace_path))
    for path in directory.rglob("*"):
        if path.is_file():
            assert SECRET not in path.read_text(encoding="utf-8", errors="replace"), path
    assert SECRET not in json.dumps(run.manifest)


# --- relanzar, purgar y retención --------------------------------------------------------------------------------


def test_relaunch_and_purge(
    user_client: TestClient, project: dict[str, object], worker: Worker, db: Session, settings: Settings
) -> None:
    run_id = str(launch(user_client, project["id"], steps=2, step_seconds=0)["id"])
    assert user_client.delete(f"/api/v1/runs/{run_id}").status_code == 409  # aún no ha terminado
    run = wait_for(worker, db, run_id)
    directory = run_dir(settings.workspace_dir, str(run.workspace_path))

    relaunched = user_client.post(f"/api/v1/runs/{run_id}/relaunch").json()
    purged = user_client.delete(f"/api/v1/runs/{run_id}")

    assert relaunched["relaunched_from"] == run_id
    assert relaunched["params"]["steps"] == 2
    assert purged.status_code == 204
    assert not directory.exists()
    detail = user_client.get(f"/api/v1/runs/{run_id}").json()
    assert (detail["status"], detail["artifacts"], detail["size_bytes"]) == ("purged", [], 0)
    db.expire_all()
    assert db.get(Run, run_id).manifest["status"] == "succeeded"  # type: ignore[union-attr]
    wait_for(worker, db, relaunched["id"])


def test_retention_by_age_and_per_project(
    user_client: TestClient, project: dict[str, object], db: Session, settings: Settings
) -> None:
    ids = [str(launch(user_client, project["id"])["id"]) for _ in range(3)]
    db.execute(update(Run).values(status="succeeded", finished_at=utcnow()))
    db.execute(update(Run).where(Run.id == ids[0]).values(finished_at=utcnow() - timedelta(days=40)))
    db.commit()

    purged = apply_retention(db, settings.model_copy(update={"run_retention_days": 30, "run_retention_per_project": 1}))

    statuses = {r.id: r.status for r in db.scalars(select(Run))}
    assert purged == 2
    assert statuses == {ids[0]: "purged", ids[1]: "purged", ids[2]: "succeeded"}


def test_health_reports_worker(client: TestClient, worker: Worker) -> None:
    assert client.get("/api/health").json()["worker"] == "ok"


def test_health_without_worker(client: TestClient) -> None:
    assert client.get("/api/health").json()["worker"] == "absent"
