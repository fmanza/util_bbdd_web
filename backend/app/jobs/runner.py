"""Subproceso de un job (ADR-002): ejecuta la operación y deja ``run.json``, ``logs/run.log`` y los artefactos.

El proceso hijo solo recibe el ``run_id``: lee la ejecución de ``config.db`` y descifra los secretos que necesite.
``finalize_run`` también la usa el worker para cerrar runs cancelados, caducados o cuyo hijo murió.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select

from app import __version__
from app.core.config import get_settings
from app.core.logging import JsonFormatter
from app.db.models import Artifact, ProjectConnection, Run, utcnow
from app.db.session import new_session
from app.domain.runs.operations import get_operation
from app.integrations.util_bbdd import library_version
from app.jobs.context import JobContext, JobError
from app.workspace.layout import (
    MANIFEST,
    RUN_LOG,
    TEMPLATES_INPUT,
    ensure_layout,
    run_dir,
    scan_artifacts,
    write_json_atomic,
)

logger = logging.getLogger("app.jobs.run")


def _configure_child_logging(log_path: Path, level: str) -> None:
    """El log del hijo va solo a ``logs/run.log`` en JSON (sin secretos: nunca se registran ``conn_params``)."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # util_bbdd y los drivers pueden registrar URLs de conexión: solo sus avisos graves.
    for name in ("util_bbdd", "sqlalchemy", "urllib3"):
        logging.getLogger(name).setLevel(logging.ERROR)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _template_inputs(directory: Path | None) -> dict[str, Any]:
    """Plantillas y avisos que dejó el job en ``inputs/templates.json`` (ADR-011); vacío si no hay o no se lee."""
    if directory is None or not (path := directory / TEMPLATES_INPUT).is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("inputs/templates.json ilegible")
        return {}
    return data if isinstance(data, dict) else {}


def _manifest(
    run: Run,
    artifacts: list[dict[str, Any]],
    connections: list[dict[str, Any]],
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Contenido de ``run.json`` (solo tipos JSON: también se guarda en ``runs.manifest``)."""
    extra = inputs or {}
    return {
        "id": run.id,
        "operation": run.operation,
        "params": run.params,
        "project": {"id": run.project_id, "name": run.project.name},
        "user": {"id": run.user_id, "username": run.user.username if run.user else None},
        "connections": connections,
        "relaunched_from": run.relaunched_from,
        "versions": {"util_bbdd_web": __version__, "util_bbdd": library_version()},
        "status": run.status,
        "error_code": run.error_code,
        "error_message": run.error_message,
        "created_at": _iso(run.created_at),
        "started_at": _iso(run.started_at),
        "finished_at": _iso(run.finished_at),
        "artifacts": artifacts,
        "templates": list(extra.get("templates", [])),
        "warnings": [str(w) for w in extra.get("warnings", [])],
    }


def _connections(db: Any, run: Run) -> list[dict[str, Any]]:
    aliases = get_operation(run.operation).connection_params(run.params) if run.operation else []
    if not aliases:
        return []
    links = db.scalars(
        select(ProjectConnection).where(
            ProjectConnection.project_id == run.project_id, ProjectConnection.alias.in_(aliases)
        )
    ).all()
    return [
        {
            "alias": link.alias,
            "connection_id": link.connection_id,
            "name": link.connection.name,
            "db_type": link.connection.db_type,
        }
        for link in links
    ]


def write_manifest(run_id: str) -> None:
    """Escribe ``run.json`` con el estado actual (sin artefactos todavía)."""
    settings = get_settings()
    with new_session() as db:
        run = db.get(Run, run_id)
        if run is None or run.workspace_path is None:
            return
        directory = run_dir(settings.workspace_dir, run.workspace_path)
        write_json_atomic(directory / MANIFEST, _manifest(run, [], _connections(db, run)))


def finalize_run(
    run_id: str,
    status: str,
    *,
    error_code: str | None = None,
    error_message: str | None = None,
    only_if_running: bool = True,
) -> bool:
    """Cierra un run: estado final, ``run.json``, artefactos registrados y tamaño.

    Returns:
        ``False`` si el run ya no estaba en curso (lo cerró otro proceso).
    """
    settings = get_settings()
    with new_session() as db:
        run = db.get(Run, run_id)
        if run is None or (only_if_running and run.status != "running"):
            return False
        run.status = status
        run.phase = "done"
        run.finished_at = utcnow()
        run.error_code = error_code
        run.error_message = (error_message or "")[:500] or None
        run.cancel_requested = False
        directory = run_dir(settings.workspace_dir, run.workspace_path) if run.workspace_path else None
        files = scan_artifacts(directory) if directory and directory.exists() else []
        listed = [
            {"path": f.path, "kind": f.kind, "size_bytes": f.size_bytes, "sha256": f.sha256}
            for f in files
            if f.path != MANIFEST
        ]
        run.manifest = _manifest(run, listed, _connections(db, run), _template_inputs(directory))
        if directory is not None:
            ensure_layout(directory)
            write_json_atomic(directory / MANIFEST, run.manifest)
            files = scan_artifacts(directory)
        db.execute(delete(Artifact).where(Artifact.run_id == run.id))
        for f in files:
            db.add(
                Artifact(run_id=run.id, path=f.path, kind=f.kind, mime=f.mime, size_bytes=f.size_bytes, sha256=f.sha256)
            )
        run.size_bytes = sum(f.size_bytes for f in files)
        db.commit()
    return True


def run_job(run_id: str) -> None:
    """Punto de entrada del subproceso (``multiprocessing`` *spawn*)."""
    from app.jobs.operations import IMPLEMENTATIONS

    settings = get_settings()
    with new_session() as db:
        run = db.get(Run, run_id)
        if run is None or run.status != "running" or run.workspace_path is None:
            return
        directory = run_dir(settings.workspace_dir, run.workspace_path)
        ctx = JobContext(
            run_id=run.id,
            project_id=run.project_id,
            operation=run.operation,
            params=dict(run.params),
            run_dir=directory,
            settings=settings,
        )
    ensure_layout(directory)
    _configure_child_logging(directory / RUN_LOG, settings.log_level)
    logger.info("Ejecución iniciada", extra={"run_id": run_id, "operation": ctx.operation})
    write_manifest(run_id)
    try:
        implementation = IMPLEMENTATIONS[ctx.operation]
        implementation(ctx)
    except JobError as exc:
        logger.info("Ejecución fallida", extra={"code": exc.code})
        finalize_run(run_id, "failed", error_code=exc.code, error_message=exc.message)
        return
    except Exception as exc:  # frontera del job: el detalle (sin mensaje, que puede llevar datos) va al log
        logger.error("Error inesperado en la ejecución", extra={"exc_type": type(exc).__name__})
        finalize_run(
            run_id, "failed", error_code="job_error", error_message=f"Error inesperado ({type(exc).__name__})."
        )
        return
    logger.info("Ejecución terminada")
    finalize_run(run_id, "succeeded")
