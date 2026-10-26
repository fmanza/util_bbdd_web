"""Fase 7: reglas de ADR-008 al encolar ``migrate_plan`` y ``migrate_apply`` (permiso + owner, destino no
``read_only`` y del motor del plan, plan sin errores, modo seco reciente, confirmación, sin relanzar, sin dos
aplicaciones a la vez), endpoints ``/plan`` y ``/migration-report`` y el permiso ``can_apply_ddl``.

Los planes se siembran directamente (fila + ``plan.json``): SQLite no es motor de migración. El flujo real contra
motores está en ``tests/integration/test_bench_migrate.py``.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.ulid import new_ulid
from app.db.models import Artifact, AuditEntry, Run, User, utcnow
from app.workspace.layout import ensure_layout, run_dir, run_relative_path, scan_artifacts
from tests.api.test_projects import login_as, new_project

PLAN: dict[str, Any] = {
    "format": 1,
    "source_engine": "postgresql",
    "target_engine": "mysql",
    "source_schema": "public",
    "error_count": 0,
    "warning_count": 1,
    "info_count": 0,
    "statements_hash": "a" * 64,
    "statements": ["CREATE TABLE clientes (id INT PRIMARY KEY)", "CREATE TABLE pedidos (id INT PRIMARY KEY)"],
    "warnings": [
        {
            "table": "clientes",
            "column": "id",
            "category": "TYPE",
            "target_type": "INT",
            "message": "integer → INT",
            "severity": "WARNING",
            "source_type": "integer",
            "proposals": [],
            "code": None,
        }
    ],
    "tables": [
        {
            "name": "clientes",
            "original_name": "clientes",
            "comment": "",
            "primary_key": ["id"],
            "columns": [
                {
                    "name": "id",
                    "original_name": "id",
                    "source_type": "integer",
                    "target_type": "INT",
                    "nullable": False,
                    "default": None,
                    "auto_increment": False,
                    "omit": False,
                }
            ],
            "indexes": [],
            "foreign_keys": [],
        }
    ],
    "views": [],
    "routines": [],
}


def _connection(client: TestClient, project_id: object, alias: str, db_type: str, *, read_only: bool) -> None:
    connection_id = client.post(
        "/api/v1/connections",
        json={
            "name": f"{alias}-{db_type}",
            "db_type": db_type,
            "params": {"host": "10.9.9.9", "user": "u", "database": "d"},
            "password": "x",
            "read_only": read_only,
        },
    ).json()["id"]
    response = client.post(
        f"/api/v1/projects/{project_id}/connections", json={"connection_id": connection_id, "alias": alias}
    )
    assert response.status_code == 201, response.text


@pytest.fixture
def project(user_client: TestClient) -> dict[str, object]:
    body = new_project(user_client)
    _connection(user_client, body["id"], "origen", "postgresql", read_only=True)
    _connection(user_client, body["id"], "destino", "mysql", read_only=False)
    _connection(user_client, body["id"], "lectura", "mysql", read_only=True)
    _connection(user_client, body["id"], "otro", "mariadb", read_only=False)
    return body


@pytest.fixture
def allowed(db: Session, user: User) -> User:
    db.execute(update(User).where(User.id == user.id).values(can_apply_ddl=True))
    db.commit()
    return user


def seed_run(
    db: Session,
    settings: Settings,
    *,
    project_id: int,
    user_id: int,
    operation: str,
    params: dict[str, Any],
    status: str = "succeeded",
    files: dict[str, str] | None = None,
    age: timedelta = timedelta(0),
) -> str:
    """Ejecución terminada con sus ficheros registrados como artefactos (como la dejaría el worker)."""
    from app.db.models import Project

    project = db.get(Project, project_id)
    assert project is not None
    run_id = new_ulid()
    created = utcnow() - age
    relative = run_relative_path(project.owner_id, project_id, created, operation, run_id)
    directory = run_dir(settings.workspace_dir, relative)
    ensure_layout(directory)
    for path, content in (files or {}).items():
        (directory / path).parent.mkdir(parents=True, exist_ok=True)
        (directory / path).write_text(content, encoding="utf-8")
    db.add(
        Run(
            id=run_id, project_id=project_id, user_id=user_id, operation=operation, params=params, status=status,
            phase="done", created_at=created, started_at=created, finished_at=created, workspace_path=relative,
        )
    )  # fmt: skip
    for artifact in scan_artifacts(directory):
        db.add(
            Artifact(
                run_id=run_id, path=artifact.path, kind=artifact.kind, mime=artifact.mime,
                size_bytes=artifact.size_bytes, sha256=artifact.sha256,
            )
        )  # fmt: skip
    db.commit()
    return run_id


def seed_plan(db: Session, settings: Settings, project: dict[str, object], user: User, **changes: Any) -> str:
    return seed_run(
        db, settings, project_id=int(str(project["id"])), user_id=user.id, operation="migrate_plan",
        params={"source_connection": "origen", "source_schema": None, "target_engine": "mysql"},
        files={"outputs/plan/plan.json": json.dumps({**PLAN, **changes})},
    )  # fmt: skip


def seed_dry_run(
    db: Session, settings: Settings, project: dict[str, object], user: User, plan_id: str, **overrides: Any
) -> str:
    params = {"plan_run": plan_id, "target_connection": "destino", "mode": "dry_run", "dry_run_run": None,
              "confirm": None, **overrides.pop("params", {})}  # fmt: skip
    return seed_run(
        db, settings, project_id=int(str(project["id"])), user_id=user.id, operation="migrate_apply",
        params=params, **overrides,
    )  # fmt: skip


def launch(client: TestClient, project_id: object, operation: str, **params: object) -> Any:
    return client.post(f"/api/v1/projects/{project_id}/runs", json={"operation": operation, "params": params})


# --- migrate_plan ------------------------------------------------------------------------------------------------


def test_plan_needs_a_supported_source_and_a_different_target(
    user_client: TestClient, project: dict[str, object], settings: Settings
) -> None:
    same = launch(user_client, project["id"], "migrate_plan", source_connection="destino", target_engine="mysql")
    ok = launch(user_client, project["id"], "migrate_plan", source_connection="origen", target_engine="mysql")
    bad_option = launch(
        user_client, project["id"], "migrate_plan", source_connection="origen", target_engine="mysql",
        charset="utf8mb4; DROP",
    )  # fmt: skip

    assert same.status_code == 422 and "distinto" in same.text
    assert ok.status_code == 202, ok.text
    assert bad_option.status_code == 422


def test_catalog_hides_apply_from_the_generic_form(user_client: TestClient) -> None:
    operations = {o["name"]: o for o in user_client.get("/api/v1/operations").json()}

    assert operations["migrate_plan"]["form"] is True
    assert operations["migrate_apply"]["form"] is False


# --- migrate_apply: quién -----------------------------------------------------------------------------------------


def test_apply_requires_the_permission(
    user_client: TestClient, project: dict[str, object], db: Session, settings: Settings, user: User
) -> None:
    plan_id = seed_plan(db, settings, project, user)

    response = launch(user_client, project["id"], "migrate_apply", plan_run=plan_id, target_connection="destino")

    assert response.status_code == 403
    assert "Puede aplicar DDL" in response.text


def test_apply_requires_owner_even_with_permission(
    user_client: TestClient,
    project: dict[str, object],
    db: Session,
    settings: Settings,
    allowed: User,
    make_user: Callable[..., User],
) -> None:
    plan_id = seed_plan(db, settings, project, allowed)
    editor = login_as(user_client, make_user, "eva")
    user_client.post(f"/api/v1/projects/{project['id']}/members", json={"username": "eva", "role": "editor"})
    eva = db.scalar(select(User).where(User.username == "eva"))
    assert eva is not None
    db.execute(update(User).where(User.id == eva.id).values(can_apply_ddl=True))
    db.commit()

    response = launch(editor, project["id"], "migrate_apply", plan_run=plan_id, target_connection="destino")

    assert response.status_code == 403
    assert "propietario" in response.text


def test_owner_with_permission_can_launch_a_dry_run_and_it_is_audited(
    user_client: TestClient, project: dict[str, object], db: Session, settings: Settings, allowed: User
) -> None:
    plan_id = seed_plan(db, settings, project, allowed)

    response = launch(user_client, project["id"], "migrate_apply", plan_run=plan_id, target_connection="destino")

    assert response.status_code == 202, response.text
    entry = db.scalars(select(AuditEntry).where(AuditEntry.target_id == response.json()["id"])).one()
    assert (entry.details or {})["migration"]["mode"] == "dry_run"
    assert (entry.details or {})["migration"]["target_connection"] == "destino"


# --- migrate_apply: qué plan y qué destino ------------------------------------------------------------------------


def test_apply_target_and_plan_rules(
    user_client: TestClient, project: dict[str, object], db: Session, settings: Settings, allowed: User
) -> None:
    plan_id = seed_plan(db, settings, project, allowed)
    blocked = seed_plan(db, settings, project, allowed, error_count=2)
    fk_blocked = seed_plan(db, settings, project, allowed, fk_blocking=True)
    noop = seed_run(
        db, settings, project_id=int(str(project["id"])), user_id=allowed.id, operation="noop", params={},
    )  # fmt: skip
    other_project = new_project(user_client, "Otro")
    foreign = seed_plan(db, settings, other_project, allowed)

    def apply(**params: object) -> Any:
        return launch(user_client, project["id"], "migrate_apply", **{"target_connection": "destino", **params})

    assert apply(plan_run=plan_id, target_connection="lectura").status_code == 422  # read_only
    assert "solo lectura" in apply(plan_run=plan_id, target_connection="lectura").text
    assert apply(plan_run=plan_id, target_connection="otro").status_code == 422  # motor distinto del plan
    assert apply(plan_run=blocked).status_code == 409
    assert apply(plan_run=fk_blocked).status_code == 409
    assert apply(plan_run=noop).status_code == 422
    assert apply(plan_run=foreign).status_code == 422
    assert apply(plan_run="01JZZZZZZZZZZZZZZZZZZZZZZZ").status_code == 422


# --- migrate_apply: modo seco y confirmación ----------------------------------------------------------------------


def test_apply_needs_a_recent_matching_dry_run_and_confirmation(
    user_client: TestClient, project: dict[str, object], db: Session, settings: Settings, allowed: User
) -> None:
    plan_id = seed_plan(db, settings, project, allowed)
    other_plan = seed_plan(db, settings, project, allowed)
    good = seed_dry_run(db, settings, project, allowed, plan_id)
    old = seed_dry_run(db, settings, project, allowed, plan_id, age=timedelta(minutes=61))
    failed = seed_dry_run(db, settings, project, allowed, plan_id, status="failed")
    wrong_plan = seed_dry_run(db, settings, project, allowed, other_plan)
    wrong_target = seed_dry_run(db, settings, project, allowed, plan_id, params={"target_connection": "otro"})

    def apply(**params: object) -> Any:
        body = {"plan_run": plan_id, "target_connection": "destino", "mode": "apply", "confirm": "destino", **params}
        return launch(user_client, project["id"], "migrate_apply", **body)

    no_dry = apply()
    assert no_dry.status_code == 422 and "modo seco" in no_dry.text
    for dry in (old, failed, wrong_plan, wrong_target):
        assert apply(dry_run_run=dry).status_code == 422, dry
    assert "60 minutos" in apply(dry_run_run=old).text
    unconfirmed = apply(dry_run_run=good, confirm="Destino")
    assert unconfirmed.status_code == 422 and "alias" in unconfirmed.text

    ok = apply(dry_run_run=good)
    assert ok.status_code == 202, ok.text
    # Otra aplicación sobre el mismo destino mientras la primera sigue en cola.
    assert apply(dry_run_run=good).status_code == 409


def test_apply_runs_cannot_be_relaunched(
    user_client: TestClient, project: dict[str, object], db: Session, settings: Settings, allowed: User
) -> None:
    plan_id = seed_plan(db, settings, project, allowed)
    dry = seed_dry_run(db, settings, project, allowed, plan_id)

    response = user_client.post(f"/api/v1/runs/{dry}/relaunch")

    assert response.status_code == 409
    assert "no se puede relanzar" in response.text


# --- lectura del plan y del informe -------------------------------------------------------------------------------


def test_plan_and_report_endpoints(
    user_client: TestClient,
    project: dict[str, object],
    db: Session,
    settings: Settings,
    allowed: User,
    make_user: Callable[..., User],
) -> None:
    plan_id = seed_plan(db, settings, project, allowed)
    report = {"mode": "dry_run", "statements_hash": "a" * 64, "statements": 2, "conflicts": ["clientes"]}
    dry = seed_dry_run(
        db, settings, project, allowed, plan_id, status="failed",
        files={"outputs/plan/report.json": json.dumps(report)},
    )  # fmt: skip
    outsider = login_as(user_client, make_user, "luis")

    plan = user_client.get(f"/api/v1/runs/{plan_id}/plan")
    got = user_client.get(f"/api/v1/runs/{dry}/migration-report")

    assert plan.status_code == 200, plan.text
    assert plan.json()["tables"][0]["columns"][0]["target_type"] == "INT"
    assert got.status_code == 200 and got.json()["conflicts"] == ["clientes"]
    assert user_client.get(f"/api/v1/runs/{dry}/plan").status_code == 404
    assert user_client.get(f"/api/v1/runs/{plan_id}/migration-report").status_code == 404
    assert outsider.get(f"/api/v1/runs/{plan_id}/plan").status_code == 404


# --- permiso can_apply_ddl ----------------------------------------------------------------------------------------


def test_admin_grants_can_apply_ddl(
    user_client: TestClient, user: User, make_user: Callable[..., User], db: Session
) -> None:
    admin = login_as(user_client, make_user, "jefa", role="admin")

    assert user_client.get("/api/v1/auth/me").json()["can_apply_ddl"] is False
    response = admin.patch(f"/api/v1/users/{user.id}", json={"can_apply_ddl": True})

    assert response.status_code == 200 and response.json()["can_apply_ddl"] is True
    assert user_client.get("/api/v1/auth/me").json()["can_apply_ddl"] is True
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "user.update")).all()[-1]
    assert (entry.details or {})["can_apply_ddl"] is True


# --- auditoría de la Fase 7: cancelación y comprobaciones en el worker --------------------------------------------


def test_running_apply_cannot_be_cancelled_but_queued_can(
    user_client: TestClient, project: dict[str, object], db: Session, settings: Settings, allowed: User
) -> None:
    plan_id = seed_plan(db, settings, project, allowed)
    running = seed_dry_run(db, settings, project, allowed, plan_id, status="running")
    queued = seed_dry_run(db, settings, project, allowed, plan_id, status="queued")

    refused = user_client.post(f"/api/v1/runs/{running}/cancel")

    assert refused.status_code == 409 and "a medias" in refused.text
    assert user_client.post(f"/api/v1/runs/{queued}/cancel").status_code == 202


def _recheck(db: Session, settings: Settings, project: dict[str, object], run_id: str) -> Any:
    from app.domain.runs.operations import MigrateApplyParams
    from app.jobs.context import JobContext
    from app.jobs.operations.migrate import _recheck as recheck

    run = db.get(Run, run_id)
    assert run is not None
    ctx = JobContext(
        run_id=run_id, project_id=int(str(project["id"])), operation="migrate_apply", params=dict(run.params),
        run_dir=run_dir(settings.workspace_dir, str(run.workspace_path)), settings=settings,
    )  # fmt: skip
    return recheck(ctx, MigrateApplyParams.model_validate(run.params))


def test_worker_uses_the_util_bbdd_plan_when_it_exists(
    project: dict[str, object], db: Session, settings: Settings, allowed: User
) -> None:
    """Desde la 1.3.0 el job reconstruye ``migration_plan.json``; los planes anteriores (sin él) se replanifican."""
    stored = {"format": "util_bbdd.migration_plan", "format_version": 1}
    new_plan = seed_run(
        db, settings, project_id=int(str(project["id"])), user_id=allowed.id, operation="migrate_plan",
        params={"source_connection": "origen", "source_schema": None, "target_engine": "mysql"},
        files={"outputs/plan/plan.json": json.dumps(PLAN), "outputs/plan/migration_plan.json": json.dumps(stored)},
    )  # fmt: skip
    old_plan = seed_plan(db, settings, project, allowed)

    assert _recheck(db, settings, project, seed_dry_run(db, settings, project, allowed, new_plan))[2] == stored
    assert _recheck(db, settings, project, seed_dry_run(db, settings, project, allowed, old_plan))[2] is None


def test_worker_rechecks_permission_owner_target_and_engine(
    user_client: TestClient,
    project: dict[str, object],
    db: Session,
    settings: Settings,
    allowed: User,
    make_user: Callable[..., User],
) -> None:
    from app.db.models import Connection, ProjectConnection
    from app.jobs.context import JobError

    plan_id = seed_plan(db, settings, project, allowed)
    run_id = seed_dry_run(db, settings, project, allowed, plan_id, status="running")
    assert _recheck(db, settings, project, run_id)[1]["statements_hash"] == "a" * 64

    def code() -> str:
        with pytest.raises(JobError) as info:
            _recheck(db, settings, project, run_id)
        return info.value.code + ": " + info.value.message

    link = db.scalars(select(ProjectConnection).where(ProjectConnection.alias == "destino")).one()
    connection = db.get(Connection, link.connection_id)
    assert connection is not None
    connection.read_only = True
    db.commit()
    assert code().startswith("forbidden: La conexión destino es de solo lectura")
    connection.read_only = False
    connection.db_type = "mariadb"
    db.commit()
    assert code().startswith("invalid_params: La conexión destino ya no es mysql")
    connection.db_type = "mysql"
    db.commit()

    db.execute(update(User).where(User.id == allowed.id).values(can_apply_ddl=False))
    db.commit()
    assert code().startswith("forbidden: El usuario ya no tiene permiso")
    db.execute(update(User).where(User.id == allowed.id).values(can_apply_ddl=True))
    db.commit()

    eva = make_user("eva")
    db.execute(update(User).where(User.id == eva.id).values(can_apply_ddl=True))
    db.execute(update(Run).where(Run.id == run_id).values(user_id=eva.id))
    db.commit()
    assert code().startswith("forbidden: El usuario ya no es miembro")
    user_client.post(f"/api/v1/projects/{project['id']}/members", json={"username": "eva", "role": "editor"})
    assert code().startswith("forbidden: Solo el propietario")

    db.execute(update(Run).where(Run.id == run_id).values(user_id=allowed.id))
    db.commit()
    assert user_client.delete(f"/api/v1/projects/{project['id']}/connections/destino").status_code == 204
    assert code().startswith("invalid_params: El proyecto ya no tiene la conexión «destino»")
