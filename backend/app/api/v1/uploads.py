"""Ficheros CSV/Excel de un proyecto para la carga bulk (Fase 9, ADR-010): subir, listar, ver columnas y borrar."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Final

from fastapi import APIRouter, File, Query, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict

from app.api.deps import Context, CurrentUser, DbSession, SettingsDep
from app.domain.projects.service import get_membership
from app.domain.runs.service import usage_bytes
from app.domain.storage.settings import effective_settings
from app.domain.uploads import files
from app.domain.uploads import service as uploads
from app.domain.uploads.errors import UploadTooLargeError

router = APIRouter(prefix="/projects", tags=["uploads"])

#: Margen sobre ``upload_max_mb`` para la cabecera ``Content-Length`` (límites del multipart y otros campos).
_MULTIPART_OVERHEAD: Final = 64 * 1024
_401: dict[int | str, dict[str, Any]] = {401: {"description": "No autenticado"}}
_404: dict[int | str, dict[str, Any]] = {404: {"description": "No existe o no eres miembro del proyecto"}}


class UploadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    kind: str
    size_bytes: int
    sha256: str
    created_at: datetime
    username: str | None = None


class UploadInfoOut(BaseModel):
    """Lo necesario para mapear columnas: columnas, primeras filas y hojas (Excel) o separador y codificación (CSV)."""

    columns: list[str]
    sample: list[list[str | None]]
    sheets: list[str] | None = None
    delimiter: str | None = None
    encoding: str | None = None


def _out(upload: Any) -> UploadOut:
    return UploadOut.model_validate(upload).model_copy(
        update={"username": upload.user.username if upload.user else None}
    )


@router.post(
    "/{project_id}/uploads", response_model=UploadOut, status_code=status.HTTP_201_CREATED, summary="Subir un fichero",
    responses={**_401, **_404, 403: {"description": "Rol inferior a editor"}, 409: {"description": "Cuota superada"},
               411: {"description": "Falta Content-Length"}, 413: {"description": "Demasiado grande"},
               415: {"description": "No es .csv ni .xlsx"},
               422: {"description": "El contenido no es válido"}},
)  # fmt: skip
def create_upload(
    project_id: int,
    request: Request,
    file: Annotated[UploadFile, File(description="Fichero .csv o .xlsx")],
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    ctx: Context,
) -> UploadOut:
    """Guarda el fichero (editores). Se comprueba el contenido real, no solo la extensión."""
    declared = int(request.headers.get("content-length") or 0)
    max_mb = effective_settings(db, settings).upload_max_mb  # administrable (ADR-012)
    if declared > max_mb * 1024 * 1024 + _MULTIPART_OVERHEAD:
        raise UploadTooLargeError(f"El máximo es {max_mb} MB.")
    membership = get_membership(db, user, project_id)
    upload = uploads.save_upload(
        db, user, membership, filename=file.filename, stream=file.file, settings=settings, ctx=ctx,
        used_bytes=usage_bytes(db, user.id),
    )  # fmt: skip
    return _out(upload)


@router.get(
    "/{project_id}/uploads", response_model=list[UploadOut], summary="Ficheros del proyecto", responses={**_401, **_404}
)
def list_uploads(project_id: int, user: CurrentUser, db: DbSession) -> list[UploadOut]:
    return [_out(u) for u in uploads.list_uploads(db, get_membership(db, user, project_id))]


@router.get(
    "/{project_id}/uploads/{upload_id}/info", response_model=UploadInfoOut, summary="Columnas de un fichero",
    responses={**_401, **_404, 422: {"description": "No se puede leer con esas opciones"}},
)  # fmt: skip
async def upload_info(
    project_id: int,
    upload_id: str,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    sheet: Annotated[str | None, Query(max_length=100)] = None,
    delimiter: Annotated[str | None, Query(pattern=r"^(,|;|\t|\|)$")] = None,
    encoding: Annotated[str | None, Query(pattern=r"^(utf-8|cp1252|latin-1)$")] = None,
) -> UploadInfoOut:
    """Columnas y primeras filas con las opciones de lectura (para el mapeo de columnas)."""
    upload = uploads.get_upload(db, get_membership(db, user, project_id), upload_id)
    path = uploads.upload_file(upload, settings)
    options = files.ReadOptions(sheet=sheet, delimiter=delimiter, encoding=encoding)
    info = await run_in_threadpool(files.describe, path, upload.kind, options)  # type: ignore[arg-type]
    return UploadInfoOut(**info)


@router.delete(
    "/{project_id}/uploads/{upload_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Borrar un fichero",
    responses={**_401, **_404, 403: {"description": "Rol inferior a editor"}, 409: {"description": "En uso"}},
)  # fmt: skip
def delete_upload(
    project_id: int, upload_id: str, user: CurrentUser, db: DbSession, settings: SettingsDep, ctx: Context
) -> None:
    membership = get_membership(db, user, project_id)
    upload = uploads.get_upload(db, membership, upload_id)
    uploads.delete_upload(db, user, membership, upload, settings=settings, ctx=ctx)
