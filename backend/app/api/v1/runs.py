"""Ejecuciones: historial por proyecto, lanzamiento (202), progreso por SSE, cancelación, relanzamiento, purga,
artefactos (descarga y vista previa segura), sitio HTML generado (URL firmada, ADR-007) y ZIP en *streaming*
(ADR-002, ADR-005)."""

from __future__ import annotations

import time
from collections.abc import AsyncIterable
from typing import Annotated, Any, Final

import anyio
from fastapi import APIRouter, Depends, Query, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.api.deps import Context, CurrentUser, DbSession, SettingsDep
from app.api.v1.schemas import MAX_PAGE_SIZE
from app.api.v1.schemas_bulk import BulkPreviewOut, BulkResultOut
from app.api.v1.schemas_diff import DiffEvolutionOut, DiffItemOut, SchemaDiffOut
from app.api.v1.schemas_dump import DumpPreviewOut, DumpResultOut
from app.api.v1.schemas_migrate import MigrationPlanOut, MigrationReportOut
from app.api.v1.schemas_projects import ArtifactOut, RunCreate, RunDetailOut, RunOut, RunPage, RunStatus
from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import site_token, verify_site_token
from app.db.models import TERMINAL_STATUSES, Artifact, Run, User
from app.db.session import new_session
from app.domain.projects.service import get_membership
from app.domain.runs import bulks, dumps, migrations, service
from app.domain.runs import diff as diff_domain
from app.domain.runs.errors import ArtifactNotFoundError, RunNotFoundError
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
#: Sitio HTML de la documentación: sus scripts se ejecutan, pero con origen opaco (sin cookies, sin ``fetch`` a la
#: API ni acceso a la SPA) y solo cargan recursos del propio servidor (ADR-007). ``frame-src 'self'``: el índice
#: muestra el detalle en un iframe propio (``detailFrame``).
SITE_CSP: Final = (
    "sandbox allow-scripts allow-popups allow-downloads; default-src 'none'; script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'none'; "
    "frame-src 'self'; form-action 'none'; base-uri 'none'"
)
#: ``frame-ancestors`` solo en el índice raíz: el padre de las demás páginas es ese índice, con origen opaco, y ningún
#: valor de ``frame-ancestors`` lo admite (ADR-007).
SITE_ROOT_CSP: Final = SITE_CSP + "; frame-ancestors 'self'"
SITE_ROOT: Final = "outputs/html/"
_TEXT_MIMES: Final = frozenset({"text/html", "text/css", "text/javascript", "image/svg+xml"})


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


def _site_url(access: service.RunAccess, user: User, settings: Settings) -> str | None:
    """URL firmada del ``index.html`` principal del sitio HTML (el menos profundo), si lo hay."""
    run = access.run
    indexes = [
        a.path
        for a in run.artifacts
        if a.kind == "html" and a.path.startswith(SITE_ROOT) and a.path.endswith("/index.html")
    ]
    if not indexes:
        return None
    index = min(indexes, key=lambda p: (p.count("/"), p))
    expires = int(time.time()) + settings.session_idle_minutes * 60
    token = site_token(settings, run_id=run.id, user_id=user.id, expires=expires)
    return f"/api/v1/runs/{run.id}/site/{token}/{index.removeprefix(SITE_ROOT)}"


def _detail(access: service.RunAccess, user: User, settings: Settings) -> RunDetailOut:
    run = access.run
    base = _run_out(run, len(run.artifacts))
    artifacts = [
        ArtifactOut.model_validate(a).model_copy(update={"previewable": _previewable(a)}) for a in run.artifacts
    ]
    return RunDetailOut(
        **base.model_dump(),
        my_role=access.membership.role,
        artifacts=artifacts,
        site_url=_site_url(access, user, settings),
    )


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
def get_run(run_id: str, user: CurrentUser, db: DbSession, settings: SettingsDep) -> RunDetailOut:
    return _detail(service.get_access(db, user, run_id), user, settings)


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
        media = "text/html; charset=utf-8" if artifact.kind == "html" else artifact.mime
        return FileResponse(
            path, media_type=media, filename=path.name, content_disposition_type="inline", headers=_SAFE_HEADERS
        )
    return PlainTextResponse(path.read_text(encoding="utf-8", errors="replace"), headers=_SAFE_HEADERS)


# --- diff de esquemas (Fase 6) ------------------------------------------------------------------------------------


def _items(items: list[diff_domain.DiffItem]) -> list[DiffItemOut]:
    return [DiffItemOut.model_validate(item, from_attributes=True) for item in items]


@router.get(
    "/{run_id}/diff", response_model=SchemaDiffOut, summary="Diff de una comparación de esquemas",
    responses={**_401, **_404, 413: {"description": "Demasiado grande para el visor"}},
)  # fmt: skip
def get_diff(run_id: str, user: CurrentUser, db: DbSession, settings: SettingsDep) -> SchemaDiffOut:
    """Diferencias del destino respecto al origen de una ejecución ``compare`` correcta."""
    access = service.get_access(db, user, run_id)
    return SchemaDiffOut.model_validate(diff_domain.load_diff(db, access.run, settings))


@router.get(
    "/{run_id}/diff/evolution", response_model=DiffEvolutionOut, summary="Evolución respecto a otra comparación",
    responses={**_401, **_404, 413: {"description": "Demasiado grande para el visor"}},
)  # fmt: skip
def get_diff_evolution(
    run_id: str,
    baseline: Annotated[str, Query(min_length=1, max_length=32, description="Id de la comparación anterior")],
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
) -> DiffEvolutionOut:
    """Diferencias nuevas, resueltas y persistentes respecto a ``baseline`` (otra comparación visible)."""
    current = diff_domain.load_diff(db, service.get_access(db, user, run_id).run, settings)
    previous = diff_domain.load_diff(db, service.get_access(db, user, baseline).run, settings)
    result = diff_domain.evolution(current, previous)
    return DiffEvolutionOut(
        run_id=run_id,
        baseline_id=baseline,
        labels_match=result.labels_match,
        new=_items(result.new),
        resolved=_items(result.resolved),
        persisting=_items(result.persisting),
    )


# --- migración DDL (Fase 7) --------------------------------------------------------------------------------------


@router.get(
    "/{run_id}/plan", response_model=MigrationPlanOut, summary="Plan de una migración DDL",
    responses={**_401, **_404, 413: {"description": "Demasiado grande para el visor"}},
)  # fmt: skip
def get_plan(run_id: str, user: CurrentUser, db: DbSession, settings: SettingsDep) -> MigrationPlanOut:
    """Plan guardado por una ejecución ``migrate_plan`` correcta (tablas, avisos y sentencias)."""
    access = service.get_access(db, user, run_id)
    return MigrationPlanOut.model_validate(migrations.load_plan(db, access.run, settings))


@router.get(
    "/{run_id}/migration-report", response_model=MigrationReportOut, summary="Informe del modo seco o de la aplicación",
    responses={**_401, **_404},
)  # fmt: skip
def get_migration_report(run_id: str, user: CurrentUser, db: DbSession, settings: SettingsDep) -> MigrationReportOut:
    """Conflictos, validación de vistas y sentencias aplicadas de una ``migrate_apply`` (también si falló)."""
    access = service.get_access(db, user, run_id)
    if access.run.operation != "migrate_apply":
        raise ArtifactNotFoundError("Esta ejecución no es una aplicación de migración.")
    _, path = service.get_artifact_by_path(db, access.run, migrations.REPORT_PATH, settings)
    return MigrationReportOut.model_validate_json(path.read_text(encoding="utf-8"))


# --- volcado de datos (Fase 8) -----------------------------------------------------------------------------------


@router.get(
    "/{run_id}/dump-preview", response_model=DumpPreviewOut, summary="Vista previa (modo seco) de un volcado",
    responses={**_401, **_404, 413: {"description": "Demasiado grande para el visor"}},
)  # fmt: skip
def get_dump_preview(run_id: str, user: CurrentUser, db: DbSession, settings: SettingsDep) -> DumpPreviewOut:
    """Orden de carga por FK, ciclos, filas y avisos por tabla de una ``dump_preview`` correcta."""
    access = service.get_access(db, user, run_id)
    return DumpPreviewOut.model_validate(dumps.load_preview(db, access.run, settings))


@router.get(
    "/{run_id}/dump-result", response_model=DumpResultOut, summary="Resultado de un volcado",
    responses={**_401, **_404, 413: {"description": "Demasiado grande para el visor"}},
)  # fmt: skip
def get_dump_result(run_id: str, user: CurrentUser, db: DbSession, settings: SettingsDep) -> DumpResultOut:
    """Filas por tabla, rechazos, constraints reactivadas y contadores PK de un ``dump_apply`` (también si falló)."""
    access = service.get_access(db, user, run_id)
    return DumpResultOut.model_validate(dumps.load_result(db, access.run, settings))


# --- carga bulk (Fase 9) -----------------------------------------------------------------------------------------


@router.get(
    "/{run_id}/bulk-preview", response_model=BulkPreviewOut, summary="Vista previa (modo seco) de una carga",
    responses={**_401, **_404},
)  # fmt: skip
def get_bulk_preview(run_id: str, user: CurrentUser, db: DbSession, settings: SettingsDep) -> BulkPreviewOut:
    """Validación, filas afectadas, plan paralelo y SQL generado de una ``bulk_preview`` correcta."""
    access = service.get_access(db, user, run_id)
    return BulkPreviewOut.model_validate(bulks.load_preview(db, access.run, settings))


@router.get(
    "/{run_id}/bulk-result", response_model=BulkResultOut, summary="Resultado de una carga", responses={**_401, **_404}
)
def get_bulk_result(run_id: str, user: CurrentUser, db: DbSession, settings: SettingsDep) -> BulkResultOut:
    """Filas antes y después, rechazos y particiones de un ``bulk_apply`` (también si falló)."""
    access = service.get_access(db, user, run_id)
    return BulkResultOut.model_validate(bulks.load_result(db, access.run, settings))


_SITE_HEADERS: Final = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "private, max-age=300",
    # Las pestañas que abre el sitio (target="_blank") heredan su sandbox, y el navegador bloquea una ventana con
    # sandbox cuya respuesta trae otro COOP (ERR_BLOCKED_BY_RESPONSE). El middleware no lo pisa (ADR-007).
    "Cross-Origin-Opener-Policy": "unsafe-none",
}


def _site_csp(path: str) -> str:
    """CSP de un fichero del sitio: solo el índice raíz (``<dir>/index.html``, el de ``site_url``) lleva
    ``frame-ancestors``."""
    return SITE_ROOT_CSP if path.count("/") == 1 and path.endswith("/index.html") else SITE_CSP


@router.get(
    "/{run_id}/site/{token}/{path:path}", summary="Sitio HTML generado (URL firmada)", response_class=FileResponse,
    responses={404: {"description": "Token no válido o caducado, sin acceso o fichero no registrado"}},
)  # fmt: skip
def site_file(run_id: str, token: str, path: str, db: DbSession, settings: SettingsDep) -> FileResponse:
    """Fichero del sitio HTML (``outputs/html/**``) para el ``iframe`` con origen opaco, que no envía la cookie.

    El token (``site_url`` del detalle) identifica al usuario; en cada petición se comprueba que sigue activo y es
    miembro del proyecto. Solo se sirven artefactos registrados de tipo ``html``.
    """
    user_id = verify_site_token(settings, token, run_id=run_id, now=int(time.time()))
    user = db.get(User, user_id) if user_id is not None else None
    if user is None or not user.is_active:
        raise RunNotFoundError()
    access = service.get_access(db, user, run_id)
    artifact, file = service.get_artifact_by_path(db, access.run, SITE_ROOT + path, settings)
    if artifact.kind != "html":
        raise ArtifactNotFoundError()
    media = f"{artifact.mime}; charset=utf-8" if artifact.mime in _TEXT_MIMES else artifact.mime
    headers = {**_SITE_HEADERS, "Content-Security-Policy": _site_csp(path)}
    return FileResponse(file, media_type=media, content_disposition_type="inline", headers=headers)


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
