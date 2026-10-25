"""Plantillas Word y Excel de la documentación (ADR-011): globales (admins) o de un proyecto (editores).

El fichero se copia en bloques a un temporal (``.tmp-<id>``) contando bytes; si supera ``template_max_mb`` se borra y
se responde 413. Después se convierte (``.dotx``/``.xltx``), se comprueba y se renombra a ``<id>.<docx|xlsx>``; el
SHA-256 es el del fichero guardado, que el job vuelve a comprobar antes de usarlo. Sin purga por antigüedad: se borran
a mano o con su proyecto.

Nombre y máximo se comprueban antes de copiar (para no guardar un fichero que se va a rechazar) y otra vez al guardar:
el índice único ``uq_document_templates_scope_kind_name`` frena los nombres repetidos y el máximo se recuenta después
del INSERT, que en SQLite ya tiene el bloqueo de escritura. Si la fila no llega a guardarse, se borra el fichero.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path, PurePath
from typing import Any, BinaryIO, Final

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.ulid import new_ulid
from app.db.models import TERMINAL_STATUSES, DocumentTemplate, Project, Run, User
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.runs.errors import RunParamsError
from app.domain.templates.errors import (
    TemplateConflictError,
    TemplateContentError,
    TemplateInUseError,
    TemplateNotFoundError,
    TemplateTooLargeError,
)
from app.domain.templates.files import STORED_SUFFIX, Kind, check_template, display_name, kind_for, untemplate
from app.workspace.layout import safe_path

logger = logging.getLogger(__name__)

_CHUNK: Final = 1024 * 1024
#: Parámetros de ``documentation`` que apuntan a una plantilla, y su tipo.
RUN_PARAMS: Final[dict[str, Kind]] = {"word_template": "word", "excel_template": "excel"}
_KIND_LABEL: Final[dict[str, str]] = {"word": "Word", "excel": "Excel"}
_UNIQUE_NAME: Final = "uq_document_templates_scope_kind_name"
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def templates_folder(workspace_dir: Path, project: Project | None) -> Path:
    """Carpeta de las plantillas globales o de un proyecto (solo IDs en la ruta)."""
    if project is None:
        return safe_path(workspace_dir, "templates")
    return safe_path(workspace_dir, f"users/{int(project.owner_id)}/projects/{int(project.id)}/templates")


def template_file(template: DocumentTemplate, settings: Settings) -> Path:
    """Ruta absoluta comprobada del fichero de ``template``.

    Raises:
        TemplateNotFoundError: Ya no está en disco.
    """
    path = safe_path(settings.workspace_dir, template.path)
    if not path.is_file():
        raise TemplateNotFoundError()
    return path


def _clean_name(name: str | None, filename: str) -> str:
    value = _CONTROL.sub("", name or "").strip() or PurePath(filename).stem
    return value[:100] or "plantilla"


def _check_name(db: Session, project_id: int | None, kind: str, name: str, exclude_id: str | None = None) -> None:
    query = select(DocumentTemplate.id).where(
        DocumentTemplate.kind == kind,
        func.lower(DocumentTemplate.name) == name.lower(),
        DocumentTemplate.project_id.is_(None) if project_id is None else DocumentTemplate.project_id == project_id,
    )
    if exclude_id is not None:
        query = query.where(DocumentTemplate.id != exclude_id)
    if db.scalar(query) is not None:
        raise _name_taken(kind, name)


def _name_taken(kind: str, name: str) -> TemplateConflictError:
    return TemplateConflictError(f"Ya hay una plantilla {_KIND_LABEL[kind]} llamada «{name}».")


def _is_name_clash(exc: IntegrityError) -> bool:
    """Si el ``IntegrityError`` es del índice de nombre único (y no, p. ej., de una clave foránea)."""
    return _UNIQUE_NAME in str(exc.orig)


def _check_limit(db: Session, project_id: int | None, settings: Settings, *, pending: int = 1) -> None:
    """Máximo de plantillas del ámbito; ``pending`` = las que se van a añadir (0 si ya está insertada)."""
    scope = DocumentTemplate.project_id.is_(None) if project_id is None else DocumentTemplate.project_id == project_id
    if (db.scalar(select(func.count()).where(scope)) or 0) + pending > settings.templates_per_scope:
        raise TemplateConflictError(f"Se ha llegado al máximo de {settings.templates_per_scope} plantillas.")


def list_templates(
    db: Session, project: Project | None, *, kind: str | None = None, include_global: bool = False
) -> list[DocumentTemplate]:
    """Plantillas de ``project`` (o las globales con ``project=None``), y las globales si ``include_global``."""
    scope: ColumnElement[bool] = DocumentTemplate.project_id.is_(None)
    if project is not None:
        scope = DocumentTemplate.project_id == project.id
        if include_global:
            scope = scope | DocumentTemplate.project_id.is_(None)
    query = select(DocumentTemplate).where(scope)
    if kind is not None:
        query = query.where(DocumentTemplate.kind == kind)
    order = (DocumentTemplate.project_id.is_(None), DocumentTemplate.kind, func.lower(DocumentTemplate.name))
    return list(db.scalars(query.order_by(*order)).all())


def get_template(
    db: Session, project: Project | None, template_id: str, *, include_global: bool = False
) -> DocumentTemplate:
    """Plantilla de ``project`` (o global con ``project=None``); 404 si es de otro ámbito (no se revela que existe)."""
    template = db.get(DocumentTemplate, template_id)
    if template is None:
        raise TemplateNotFoundError()
    own = template.project_id == (project.id if project is not None else None)
    if not own and not (include_global and template.project_id is None):
        raise TemplateNotFoundError()
    return template


def _store(stream: BinaryIO, tmp: Path, limit: int, max_mb: int) -> None:
    size = 0
    with tmp.open("wb") as out:
        while chunk := stream.read(_CHUNK):
            size += len(chunk)
            if size > limit:
                raise TemplateTooLargeError(f"El máximo es {max_mb} MB.")
            out.write(chunk)


def save_template(
    db: Session,
    user: User,
    project: Project | None,
    *,
    name: str | None,
    filename: str | None,
    stream: BinaryIO,
    settings: Settings,
    ctx: RequestContext,
) -> DocumentTemplate:
    """Guarda una plantilla global (``project=None``) o de un proyecto; los permisos los comprueba quien llama.

    Raises:
        TemplateTypeError, TemplateTooLargeError, TemplateContentError, TemplateConflictError.
    """
    shown = display_name(filename)
    kind, from_template = kind_for(shown)
    clean = _clean_name(name, shown)
    project_id = project.id if project is not None else None
    _check_name(db, project_id, kind, clean)
    _check_limit(db, project_id, settings)
    folder = templates_folder(settings.workspace_dir, project)
    folder.mkdir(parents=True, exist_ok=True)
    template_id = new_ulid()
    tmp = folder / f".tmp-{template_id}.{STORED_SUFFIX[kind]}"  # openpyxl exige la extensión
    try:
        _store(stream, tmp, settings.template_max_mb * 1024 * 1024, settings.template_max_mb)
        if from_template:
            untemplate(tmp, kind)
        info = check_template(tmp, kind, max_uncompressed=settings.upload_max_uncompressed_mb * 1024 * 1024)
        final = folder / f"{template_id}.{STORED_SUFFIX[kind]}"
        tmp.replace(final)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    data = final.read_bytes()
    template = DocumentTemplate(
        id=template_id, project_id=project_id, kind=kind, name=clean, filename=shown,
        path=final.relative_to(settings.workspace_dir.resolve()).as_posix(), size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(), table_style=info.table_style, table_styles=info.table_styles,
        created_by=user.id,
    )  # fmt: skip
    try:
        db.add(template)
        db.flush()  # el INSERT toma el bloqueo de escritura de SQLite: el recuento de abajo ya no tiene carreras
        _check_limit(db, project_id, settings, pending=0)
        audit.record(
            db, action=AuditAction.TEMPLATE_CREATE, ctx=ctx, actor_id=user.id, target_type="template",
            target_id=template_id, details={"project_id": project_id, "kind": kind, "name": clean, "filename": shown},
        )  # fmt: skip
        db.commit()
    except BaseException as exc:
        db.rollback()
        final.unlink(missing_ok=True)  # sin fila no queda fichero
        if isinstance(exc, IntegrityError) and _is_name_clash(exc):
            raise _name_taken(kind, clean) from None
        raise
    return template


def update_template(
    db: Session, user: User, template: DocumentTemplate, *, name: str | None, table_style: str | None,
    ctx: RequestContext,
) -> DocumentTemplate:  # fmt: skip
    """Cambia el nombre o el estilo de tabla (uno de ``table_styles``).

    Raises:
        TemplateConflictError: Nombre repetido.
        TemplateContentError: Estilo de tabla que no está en la plantilla.
    """
    changes: dict[str, Any] = {}
    if name is not None:
        clean = _clean_name(name, template.filename)
        if clean != template.name:
            _check_name(db, template.project_id, template.kind, clean, exclude_id=template.id)
            changes["name"] = template.name = clean
    if table_style is not None and table_style != template.table_style:
        if table_style not in template.table_styles:
            raise TemplateContentError(f"La plantilla no tiene el estilo de tabla «{table_style}».")
        changes["table_style"] = template.table_style = table_style
    if changes:
        audit.record(
            db, action=AuditAction.TEMPLATE_UPDATE, ctx=ctx, actor_id=user.id, target_type="template",
            target_id=template.id, details={"project_id": template.project_id, **changes},
        )  # fmt: skip
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            if _is_name_clash(exc):
                raise _name_taken(template.kind, str(changes.get("name", template.name))) from None
            raise
    return template


def in_use(db: Session, template: DocumentTemplate) -> bool:
    """La usa una documentación en cola o en curso (de su proyecto o, si es global, de cualquiera)."""
    query = select(Run).where(Run.operation == "documentation", Run.status.not_in((*TERMINAL_STATUSES, "purged")))
    if template.project_id is not None:
        query = query.where(Run.project_id == template.project_id)
    return any(template.id in (run.params.get(key) for key in RUN_PARAMS) for run in db.scalars(query).all())


def delete_template(
    db: Session, user: User, template: DocumentTemplate, *, settings: Settings, ctx: RequestContext
) -> None:
    """Borra la plantilla y su fichero (las ejecuciones ya hechas tienen su copia en ``inputs/``).

    Raises:
        TemplateInUseError: La usa una documentación en cola o en curso.
    """
    if in_use(db, template):
        raise TemplateInUseError()
    try:
        safe_path(settings.workspace_dir, template.path).unlink(missing_ok=True)
    except ValueError:  # ruta guardada fuera del workspace: no se toca nada
        logger.warning("Ruta de plantilla fuera del workspace", extra={"template_id": template.id})
    db.delete(template)
    audit.record(
        db, action=AuditAction.TEMPLATE_DELETE, ctx=ctx, actor_id=user.id, target_type="template",
        target_id=template.id, details={"project_id": template.project_id, "kind": template.kind,
                                        "name": template.name},
    )  # fmt: skip
    db.commit()


def resolve_for_run(db: Session, project: Project, template_id: str, kind: str) -> DocumentTemplate | None:
    """Plantilla que puede usar una documentación de ``project``: suya o global y del tipo pedido."""
    template = db.get(DocumentTemplate, template_id)
    if template is None or template.kind != kind or template.project_id not in (None, project.id):
        return None
    return template


def check_run_templates(db: Session, project: Project, params: dict[str, Any]) -> None:
    """Al encolar una documentación: cada plantilla elegida es del proyecto o global, y del tipo correcto.

    Raises:
        RunParamsError: Con el campo en ``errors``.
    """
    for key, kind in RUN_PARAMS.items():
        template_id = params.get(key)
        if template_id and resolve_for_run(db, project, str(template_id), kind) is None:
            message = f"La plantilla {_KIND_LABEL[kind]} no existe en el proyecto ni en el catálogo global."
            raise RunParamsError(
                message, errors=[{"loc": ["body", "params", key], "msg": message, "type": "value_error"}]
            )
