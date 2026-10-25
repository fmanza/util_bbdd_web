"""Plantillas Word y Excel de la documentación (ADR-011).

- ``/document-templates``: catálogo global (cualquier usuario lo ve y descarga) y plantillas base.
- ``/admin/document-templates``: alta, cambio y borrado de las globales (``admin``).
- ``/projects/{id}/document-templates``: las del proyecto más las globales (miembros); alta, cambio y borrado
  (editores).
"""

from __future__ import annotations

from pathlib import PurePath
from typing import Annotated, Any, Final

from fastapi import APIRouter, File, Form, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, Response

from app.api.deps import AdminUser, Context, CurrentUser, DbSession, SettingsDep
from app.api.v1.schemas_templates import TemplateKind, TemplateOut, TemplateUpdate
from app.core.config import Settings
from app.db.models import DocumentTemplate, Project
from app.domain.projects.service import get_membership
from app.domain.templates import service
from app.domain.templates.errors import TemplateTooLargeError
from app.domain.templates.files import STORED_SUFFIX, base_template
from app.workspace.layout import mime_type

router = APIRouter(prefix="/document-templates", tags=["templates"])
admin_router = APIRouter(prefix="/admin/document-templates", tags=["admin"])
project_router = APIRouter(prefix="/projects/{project_id}/document-templates", tags=["templates"])

#: Margen sobre ``template_max_mb`` para la cabecera ``Content-Length`` (límites del multipart y el nombre).
_MULTIPART_OVERHEAD: Final = 64 * 1024
_SAFE_HEADERS: Final = {"X-Content-Type-Options": "nosniff"}
_401: dict[int | str, dict[str, Any]] = {401: {"description": "No autenticado"}}
_404: dict[int | str, dict[str, Any]] = {404: {"description": "No existe o no es visible"}}
_ADMIN: dict[int | str, dict[str, Any]] = {**_401, 403: {"description": "Sin rol de administrador o CSRF no válido"}}
_EDITOR: dict[int | str, dict[str, Any]] = {
    **_401, **_404, 403: {"description": "Rol inferior a editor o CSRF no válido"}
}  # fmt: skip
_UPLOAD: dict[int | str, dict[str, Any]] = {
    409: {"description": "Nombre repetido o límite de plantillas"},
    413: {"description": "Demasiado grande"},
    415: {"description": "No es .docx, .dotx, .xlsx ni .xltx (o tiene macros)"},
    422: {"description": "Contenido no válido, no seguro o (Word) le faltan estilos"},
}
_FILE_FIELD = File(description="Plantilla .docx, .dotx, .xlsx o .xltx")
_NAME_FIELD = Form(max_length=100, description="Nombre visible; vacío = el del fichero")
KindQuery = Annotated[TemplateKind | None, Query(description="Solo plantillas de este tipo")]


def _out(template: DocumentTemplate) -> TemplateOut:
    fields = set(TemplateOut.model_fields) - {"scope", "username"}
    return TemplateOut.model_validate({
        **{name: getattr(template, name) for name in fields},
        "scope": "global" if template.project_id is None else "project",
        "username": template.user.username if template.user else None,
    })  # fmt: skip


def _check_length(request: Request, settings: Settings) -> None:
    declared = int(request.headers.get("content-length") or 0)
    if declared > settings.template_max_mb * 1024 * 1024 + _MULTIPART_OVERHEAD:
        raise TemplateTooLargeError(f"El máximo es {settings.template_max_mb} MB.")


def _file(template: DocumentTemplate, settings: Settings) -> FileResponse:
    path = service.template_file(template, settings)
    name = f"{PurePath(template.filename).stem}.{STORED_SUFFIX[template.kind]}"
    return FileResponse(
        path, media_type=mime_type(name), filename=name, content_disposition_type="attachment", headers=_SAFE_HEADERS
    )


# --- catálogo global ---------------------------------------------------------------------------------------------


@router.get("", response_model=list[TemplateOut], summary="Plantillas globales", responses=_401)
def list_global(_: CurrentUser, db: DbSession, kind: KindQuery = None) -> list[TemplateOut]:
    return [_out(t) for t in service.list_templates(db, None, kind=kind)]


@router.get(
    "/base/{kind}", summary="Plantilla base", response_class=Response,
    responses={**_401, 200: {"description": "Word con los estilos que usa la documentación, o Excel de ejemplo"}},
)  # fmt: skip
def download_base(kind: TemplateKind, _: CurrentUser) -> Response:
    """Punto de partida con todos los estilos necesarios (Word en horizontal; Excel con encabezado y pie)."""
    name = f"plantilla_base.{STORED_SUFFIX[kind]}"
    return Response(
        base_template(kind),
        media_type=mime_type(name),
        headers={**_SAFE_HEADERS, "Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get(
    "/{template_id}/file", summary="Descargar una plantilla global", response_class=FileResponse,
    responses={**_401, **_404},
)  # fmt: skip
def download_global(template_id: str, _: CurrentUser, db: DbSession, settings: SettingsDep) -> FileResponse:
    return _file(service.get_template(db, None, template_id), settings)


# --- administración de las globales ------------------------------------------------------------------------------


@admin_router.post(
    "", response_model=TemplateOut, status_code=status.HTTP_201_CREATED, summary="Subir una plantilla global",
    responses={**_ADMIN, **_UPLOAD},
)  # fmt: skip
def create_global(
    request: Request,
    file: Annotated[UploadFile, _FILE_FIELD],
    admin: AdminUser,
    db: DbSession,
    settings: SettingsDep,
    ctx: Context,
    name: Annotated[str | None, _NAME_FIELD] = None,
) -> TemplateOut:
    """Se comprueba el contenido real: tipo, macros, objetos y vínculos externos y, en Word, los estilos."""
    _check_length(request, settings)
    template = service.save_template(
        db, admin, None, name=name, filename=file.filename, stream=file.file, settings=settings, ctx=ctx
    )
    return _out(template)


@admin_router.patch(
    "/{template_id}", response_model=TemplateOut, summary="Cambiar una plantilla global",
    responses={**_ADMIN, **_404, 409: {"description": "Nombre repetido"},
               422: {"description": "Estilo de tabla que no está en la plantilla"}},
)  # fmt: skip
def update_global(template_id: str, body: TemplateUpdate, admin: AdminUser, db: DbSession, ctx: Context) -> TemplateOut:
    template = service.get_template(db, None, template_id)
    return _out(service.update_template(db, admin, template, name=body.name, table_style=body.table_style, ctx=ctx))


@admin_router.delete(
    "/{template_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Borrar una plantilla global",
    responses={**_ADMIN, **_404, 409: {"description": "La usa una documentación en cola o en curso"}},
)  # fmt: skip
def delete_global(template_id: str, admin: AdminUser, db: DbSession, settings: SettingsDep, ctx: Context) -> None:
    template = service.get_template(db, None, template_id)
    service.delete_template(db, admin, template, settings=settings, ctx=ctx)


# --- plantillas de un proyecto -----------------------------------------------------------------------------------


def _project(db: DbSession, user: CurrentUser, project_id: int, *, editor: bool) -> Project:
    return get_membership(db, user, project_id, "editor" if editor else "viewer").project


@project_router.get(
    "", response_model=list[TemplateOut], summary="Plantillas del proyecto y globales", responses={**_401, **_404}
)
def list_project(project_id: int, user: CurrentUser, db: DbSession, kind: KindQuery = None) -> list[TemplateOut]:
    project = _project(db, user, project_id, editor=False)
    return [_out(t) for t in service.list_templates(db, project, kind=kind, include_global=True)]


@project_router.post(
    "", response_model=TemplateOut, status_code=status.HTTP_201_CREATED, summary="Subir una plantilla al proyecto",
    responses={**_EDITOR, **_UPLOAD},
)  # fmt: skip
def create_project_template(
    project_id: int,
    request: Request,
    file: Annotated[UploadFile, _FILE_FIELD],
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    ctx: Context,
    name: Annotated[str | None, _NAME_FIELD] = None,
) -> TemplateOut:
    """Editores. Se comprueba el contenido real como en las globales."""
    _check_length(request, settings)
    project = _project(db, user, project_id, editor=True)
    template = service.save_template(
        db, user, project, name=name, filename=file.filename, stream=file.file, settings=settings, ctx=ctx
    )
    return _out(template)


@project_router.patch(
    "/{template_id}", response_model=TemplateOut, summary="Cambiar una plantilla del proyecto",
    responses={**_EDITOR, 409: {"description": "Nombre repetido"},
               422: {"description": "Estilo de tabla que no está en la plantilla"}},
)  # fmt: skip
def update_project_template(
    project_id: int, template_id: str, body: TemplateUpdate, user: CurrentUser, db: DbSession, ctx: Context
) -> TemplateOut:
    template = service.get_template(db, _project(db, user, project_id, editor=True), template_id)
    return _out(service.update_template(db, user, template, name=body.name, table_style=body.table_style, ctx=ctx))


@project_router.delete(
    "/{template_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Borrar una plantilla del proyecto",
    responses={**_EDITOR, 409: {"description": "La usa una documentación en cola o en curso"}},
)  # fmt: skip
def delete_project_template(
    project_id: int, template_id: str, user: CurrentUser, db: DbSession, settings: SettingsDep, ctx: Context
) -> None:
    template = service.get_template(db, _project(db, user, project_id, editor=True), template_id)
    service.delete_template(db, user, template, settings=settings, ctx=ctx)


@project_router.get(
    "/{template_id}/file", summary="Descargar una plantilla del proyecto o global", response_class=FileResponse,
    responses={**_401, **_404},
)  # fmt: skip
def download_project_template(
    project_id: int, template_id: str, user: CurrentUser, db: DbSession, settings: SettingsDep
) -> FileResponse:
    project = _project(db, user, project_id, editor=False)
    return _file(service.get_template(db, project, template_id, include_global=True), settings)
