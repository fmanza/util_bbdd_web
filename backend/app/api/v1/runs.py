"""Ejecuciones: historial por proyecto, lanzamiento (202), progreso por SSE, cancelación, relanzamiento, purga,
artefactos (descarga y vista previa segura) y ZIP en *streaming* (ADR-002, ADR-005)."""

from __future__ import annotations

from collections.abc import AsyncIterable
from typing import Annotated, Any, Final

import anyio
from fastapi import APIRouter, Depends, Query, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.api.deps import Context, CurrentUser, DbSession, SettingsDep
from app.api.v1.schemas import MAX_PAGE_SIZE
from app.api.v1.schemas_projects import ArtifactOut, RunCreate, RunDetailOut, RunOut, RunPage, RunStatus
from app.core.errors import AppError
from app.db.models import TERMINAL_STATUSES, Artifact, Run
from app.db.session import new_session
from app.domain.projects.service import get_membership
from app.domain.runs import service
from app.domain.runs.errors import ArtifactNotFoundError
from app.domain.runs.service import RunFilters
from app.workspace.layout import run_dir, zip_stream

project_router = APIRouter(prefix="/projects", tags=["runs"])
router = APIRouter(prefix="/runs", tags=["runs"])

_401: dict[int | str, dict[str, Any]] = {401: {"description": "No autenticado"}}
_404: dict[int | str, dict[str, Any]] = {404: {"description": "No existe o no eres miembro del proyecto"}}
_403: dict[int | str, dict[str, Any]] = {403: {"description": "Tu rol no lo permite o CSRF no válido"}}

#: Tipos con vista previa: HTML y SVG en ``iframe sandbox``; el resto como texto plano.
SANDBOXED_KINDS: Final = frozenset({"html", "graphs"})
TEXT_KINDS: Final = frozenset({"markdown", "sql", "log", "manifest"})
PREVIEW_MAX_BYTES: Final = 2 * 1024 * 1024
SSE_POLL_SECONDS: Final = 1.0
#: CSP de las vistas previas: sin scripts, sin peticiones salientes, origen opaco (``sandbox``).
PREVIEW_CSP: Final = "sandbox; default-src 'none'; img-src data:; style-src 'unsafe-inline'; frame-ancestors 'self'"


class PreviewUnavailableError(AppError):
    status = 415
    title = "Este artefacto no tiene vista previa"


class PreviewTooLargeError(AppError):
    status = 413
    title = "El artefacto es demasiado grande para la vista previa; descárgalo"


def _previewable(artifact: Artifact) -> bool:
    return artifact.kind in SANDBOXED_KINDS or artifact.kind in TEXT_KINDS


def _run_out(run: Run, artifacts_count: int) -> RunOut:
    duration = (run.finished_at - run.started_at).total_seconds() if run.finished_at and run.started_at else None
    status_value: RunStatus = run.status  # type: ignore[assignment]
    return RunOut(
        id=run.id,
        project_id=run.project_id,
        project_name=run.project.name,
        operation=run.operation,
        params=run.params,
        status=status_value,
        phase=run.phase,
        progress_message=run.progress_message,
        progress_pct=run.progress_pct,
        error_code=run.error_code,
        error_message=run.error_message,
        cancel_requested=run.cancel_requested,
        user_id=run.user_id,
        username=run.user.username if run.user else None,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_seconds=duration,
        size_bytes=run.size_bytes,
        artifacts_count=artifacts_count,
        relaunched_from=run.relaunched_from,
    )


def _page(db: Any, rows: list[Run], total: int) -> RunPage:
    counts = service.artifact_count(db, [r.id for r in rows])
    return RunPage(items=[_run_out(r, counts.get(r.id, 0)) for r in rows], total=total)


def _detail(access: service.RunAccess) -> RunDetailOut:
    run = access.run
    base = _run_out(run, len(run.artifacts))
    artifacts = [
        ArtifactOut.model_validate(a).model_copy(update={"previewable": _previewable(a)}) for a in run.artifacts
    ]
    return RunDetailOut(**base.model_dump(), my_role=access.membership.role, artifacts=artifacts)


def _filters(status_filter: RunStatus | None, operation: str | None, user_id: int | None, q: str | None) -> RunFilters:
    return RunFilters(status=status_filter, operation=operation, user_id=user_id, q=q)


# --- historial y lanzamiento -------------------------------------------------------------------------------------


@project_router.get(
    "/{project_id}/runs", response_model=RunPage, summary="Historial de ejecuciones", responses={**_401, **_404}
)
def list_project_runs(
    project_id: int,
    user: CurrentUser,
    db: DbSession,
    status_filter: Annotated[RunStatus | None, Query(alias="status")] = None,
    operation: Annotated[str | None, Query(max_length=32)] = None,
    user_id: Annotated[int | None, Query(ge=1)] = None,
    q: Annotated[str | None, Query(max_length=100, description="Id, operación, usuario o mensaje")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RunPage:
    """Una fila por ejecución, más recientes primero, con el número de artefactos."""
    membership = get_membership(db, user, project_id)
    rows, total = service.list_project_runs(
        db, membership.project, _filters(status_filter, operation, user_id, q), limit=limit, offset=offset
    )
    return _page(db, rows, total)


@project_router.post(
    "/{project_id}/runs",
    response_model=RunOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Lanzar ejecución",
    responses={
        **_401, **_403, **_404,
        409: {"description": "Cuota de almacenamiento superada"},
        422: {"description": "Operación o parámetros no válidos"},
        429: {"description": "Demasiadas ejecuciones en cola"},
    },
)  # fmt: skip
def create_run(
    project_id: int, body: RunCreate, user: CurrentUser, db: DbSession, settings: SettingsDep, ctx: Context
) -> RunOut:
    """Encola la ejecución (editores); el worker la ejecuta en un subproceso. Sigue el progreso en ``/events``."""
    membership = get_membership(db, user, project_id)
    run = service.enqueue(
        db, user, membership, operation=body.operation, params=body.params, settings=settings, ctx=ctx
    )
    return _run_out(run, 0)


@router.get("", response_model=RunPage, summary="Mis ejecuciones recientes", responses=_401)
def list_my_runs(
    user: CurrentUser,
    db: DbSession,
    status_filter: Annotated[RunStatus | None, Query(alias="status")] = None,
    operation: Annotated[str | None, Query(max_length=32)] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RunPage:
    """Ejecuciones de todos los proyectos de los que eres miembro."""
    rows, total = service.list_user_runs(
        db, user, _filters(status_filter, operation, None, q), limit=limit, offset=offset
    )
    return _page(db, rows, total)


# --- una ejecución -----------------------------------------------------------------------------------------------


@router.get("/{run_id}", response_model=RunDetailOut, summary="Ver ejecución", responses={**_401, **_404})
def get_run(run_id: str, user: CurrentUser, db: DbSession) -> RunDetailOut:
    return _detail(service.get_access(db, user, run_id))


def visible_run(run_id: str, user: CurrentUser, db: DbSession) -> service.RunAccess:
    """Comprueba el acceso **antes** de abrir el stream SSE (un error dentro del generador ya no puede ser un 404)."""
    return service.get_access(db, user, run_id)


VisibleRun = Annotated[service.RunAccess, Depends(visible_run)]


def _snapshot(run_id: str) -> dict[str, Any] | None:
    with new_session() as db:
        run = db.get(Run, run_id)
        if run is None:
            return None
        count = service.artifact_count(db, [run_id]).get(run_id, 0)
        return _run_out(run, count).model_dump(mode="json")


@router.get(
    "/{run_id}/events",
    response_class=EventSourceResponse,
    summary="Progreso en vivo (SSE)",
    responses={**_401, **_404},
)
async def run_events(run_id: str, _: VisibleRun) -> AsyncIterable[ServerSentEvent]:
    """Eventos ``run`` (instantánea al cambiar) y ``end`` al terminar; *keepalive* periódico."""
    last: dict[str, Any] | None = None
    while True:
        snapshot = await run_in_threadpool(_snapshot, run_id)
        if snapshot is None:
            yield ServerSentEvent(event="end", data={"id": run_id, "status": "gone"})
            return
        if snapshot != last:
            yield ServerSentEvent(
                event="run", data=snapshot, id=f"{run_id}-{snapshot['phase']}-{snapshot['progress_pct']}"
            )
            last = snapshot
        if snapshot["status"] in TERMINAL_STATUSES or snapshot["status"] == "purged":
            yield ServerSentEvent(event="end", data={"id": run_id, "status": snapshot["status"]})
            return
        await anyio.sleep(SSE_POLL_SECONDS)


@router.post(
    "/{run_id}/cancel", response_model=RunOut, status_code=status.HTTP_202_ACCEPTED, summary="Cancelar",
    responses={**_401, **_403, **_404, 409: {"description": "Ya terminó"}},
)  # fmt: skip
def cancel_run(run_id: str, user: CurrentUser, db: DbSession, ctx: Context) -> RunOut:
    """En cola: se cancela al momento. En curso: el worker termina su subproceso."""
    access = service.get_access(db, user, run_id)
    run = service.cancel(db, user, access, ctx=ctx)
    return _run_out(run, len(run.artifacts))


@router.post(
    "/{run_id}/relaunch", response_model=RunOut, status_code=status.HTTP_202_ACCEPTED, summary="Relanzar",
    responses={**_401, **_403, **_404, 409: {"description": "Cuota superada"}, 429: {"description": "Cola llena"}},
)  # fmt: skip
def relaunch_run(run_id: str, user: CurrentUser, db: DbSession, settings: SettingsDep, ctx: Context) -> RunOut:
    """Nueva ejecución con la misma operación y parámetros."""
    access = service.get_access(db, user, run_id)
    return _run_out(service.relaunch(db, user, access, settings=settings, ctx=ctx), 0)


@router.delete(
    "/{run_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Purgar ejecución",
    responses={**_401, **_403, **_404, 409: {"description": "No ha terminado"}},
)  # fmt: skip
def purge_run(run_id: str, user: CurrentUser, db: DbSession, settings: SettingsDep, ctx: Context) -> None:
    """Borra los ficheros de una ejecución terminada; se conserva su resumen (``manifest``)."""
    access = service.get_access(db, user, run_id)
    service.purge(db, user, access, settings=settings, ctx=ctx)


# --- artefactos --------------------------------------------------------------------------------------------------

_SAFE_HEADERS: Final = {"X-Content-Type-Options": "nosniff", "Content-Security-Policy": PREVIEW_CSP}


@router.get(
    "/{run_id}/artifacts/{artifact_id}", summary="Descargar artefacto", response_class=FileResponse,
    responses={**_401, **_404},
)  # fmt: skip
def download_artifact(
    run_id: str, artifact_id: int, user: CurrentUser, db: DbSession, settings: SettingsDep
) -> FileResponse:
    access = service.get_access(db, user, run_id)
    artifact, path = service.get_artifact(db, access.run, artifact_id, settings)
    return FileResponse(
        path,
        media_type=artifact.mime,
        filename=path.name,
        content_disposition_type="attachment",
        headers=_SAFE_HEADERS,
    )


@router.get(
    "/{run_id}/artifacts/{artifact_id}/preview",
    summary="Vista previa de un artefacto",
    response_model=None,
    responses={**_401, **_404, 413: {"description": "Demasiado grande"}, 415: {"description": "Sin vista previa"}},
)
def preview_artifact(
    run_id: str, artifact_id: int, user: CurrentUser, db: DbSession, settings: SettingsDep
) -> Response:
    """HTML y SVG con CSP ``sandbox`` (para un ``iframe sandbox``); Markdown, SQL, log y ``run.json`` como texto."""
    access = service.get_access(db, user, run_id)
    artifact, path = service.get_artifact(db, access.run, artifact_id, settings)
    if not _previewable(artifact):
        raise PreviewUnavailableError()
    if artifact.size_bytes > PREVIEW_MAX_BYTES:
        raise PreviewTooLargeError()
    if artifact.kind in SANDBOXED_KINDS:
        media = "image/svg+xml" if path.suffix.lower() == ".svg" else "text/html; charset=utf-8"
        return FileResponse(
            path, media_type=media, filename=path.name, content_disposition_type="inline", headers=_SAFE_HEADERS
        )
    return PlainTextResponse(path.read_text(encoding="utf-8", errors="replace"), headers=_SAFE_HEADERS)


@router.get(
    "/{run_id}/archive", summary="Descargar ZIP de la ejecución", response_class=StreamingResponse,
    responses={**_401, **_404},
)  # fmt: skip
def download_archive(run_id: str, user: CurrentUser, db: DbSession, settings: SettingsDep) -> StreamingResponse:
    """ZIP generado al vuelo con todos los artefactos registrados."""
    access = service.get_access(db, user, run_id)
    run = access.run
    if run.workspace_path is None or not run.artifacts:
        raise ArtifactNotFoundError("La ejecución no tiene artefactos.")
    directory = run_dir(settings.workspace_dir, run.workspace_path)
    prefix = directory.name
    return StreamingResponse(
        zip_stream(directory, [a.path for a in run.artifacts], prefix=prefix),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{prefix}.zip"', "X-Content-Type-Options": "nosniff"},
    )
