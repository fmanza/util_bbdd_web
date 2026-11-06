"""``/api/v1/admin/runs``: ejecuciones de todos los proyectos y su borrado (solo ``admin``).

Solo metadatos (nunca ``params``, mensajes ni artefactos): un admin no miembro no ve el contenido de un proyecto.
Sesión ``2026-11-06-explorer-runs-lists`` (D1-D3, D8).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, Context, DbSession, SettingsDep
from app.api.v1.schemas import MAX_PAGE_SIZE
from app.api.v1.schemas_admin_runs import (
    AdminRunOut,
    AdminRunPage,
    ProjectRunsDelete,
    ProjectRunsDeleteOut,
    ProjectRunsSummaryOut,
)
from app.api.v1.schemas_projects import RunStatus
from app.domain.runs import admin
from app.domain.runs.admin import AdminRunSort
from app.domain.sorting import SortOrder

router = APIRouter(prefix="/admin", tags=["admin"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    403: {"description": "Sin rol de administrador o CSRF no válido"},
}


@router.get("/runs", response_model=AdminRunPage, summary="Ejecuciones de todos los proyectos", responses=_ERRORS)
def list_runs(
    _: AdminUser,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=100, description="Id, proyecto, operación o usuario")] = None,
    project_id: Annotated[int | None, Query(ge=1)] = None,
    status_filter: Annotated[RunStatus | None, Query(alias="status")] = None,
    sort: AdminRunSort | None = None,
    order: SortOrder | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminRunPage:
    rows, total = admin.list_all_runs(
        db, q=q, project_id=project_id, status=status_filter, sort=sort, order=order, limit=limit, offset=offset
    )
    return AdminRunPage(items=[AdminRunOut.model_validate(r, from_attributes=True) for r in rows], total=total)


@router.delete(
    "/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar una ejecución",
    responses={**_ERRORS, 404: {"description": "No existe"}, 409: {"description": "Activa o volcado pendiente"}},
)  # fmt: skip
def delete_run(run_id: str, user: AdminUser, db: DbSession, settings: SettingsDep, ctx: Context) -> None:
    """Borra la fila, los artefactos y la carpeta; desaparece del historial (la auditoría guarda el resumen)."""
    admin.delete_run(db, user, run_id, settings=settings, ctx=ctx)


@router.get(
    "/projects/{project_id}/runs/summary", response_model=ProjectRunsSummaryOut,
    summary="Ejecuciones de un proyecto (para confirmar el borrado)",
    responses={**_ERRORS, 404: {"description": "No existe"}},
)  # fmt: skip
def project_runs_summary(project_id: int, _: AdminUser, db: DbSession) -> ProjectRunsSummaryOut:
    project, count, size = admin.project_runs_summary(db, project_id)
    return ProjectRunsSummaryOut(project_id=project.id, project_name=project.name, runs=count, size_bytes=size)


@router.post(
    "/projects/{project_id}/runs/delete", response_model=ProjectRunsDeleteOut,
    summary="Eliminar las ejecuciones de un proyecto",
    responses={**_ERRORS, 404: {"description": "No existe"}, 422: {"description": "Confirmación incorrecta"}},
)  # fmt: skip
def delete_project_runs(
    project_id: int, body: ProjectRunsDelete, user: AdminUser, db: DbSession, settings: SettingsDep, ctx: Context
) -> ProjectRunsDeleteOut:
    """Borra las terminadas; omite las activas y los volcados con constraints sin restaurar y dice cuántas."""
    result = admin.delete_project_runs(db, user, project_id, body.confirm, settings=settings, ctx=ctx)
    return ProjectRunsDeleteOut.model_validate(result, from_attributes=True)
