"""Subidas de ficheros a un proyecto para la carga bulk (Fase 9, ADR-010).

El fichero se copia en bloques a un temporal de la carpeta del proyecto (``…/uploads/.tmp-<id>``) contando bytes y
calculando el SHA-256; si supera ``upload_max_mb`` se borra y se responde 413. Después se comprueba el contenido y se
renombra a ``<id>.<ext>``. Los ficheros cuentan en la cuota del usuario.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import BinaryIO, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.ulid import new_ulid
from app.db.models import TERMINAL_STATUSES, Run, Upload, User, utcnow
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.projects.errors import ProjectForbiddenError
from app.domain.projects.service import Membership
from app.domain.uploads.errors import UploadInUseError, UploadNotFoundError, UploadQuotaError, UploadTooLargeError
from app.domain.uploads.files import check_content, display_name, kind_for
from app.workspace.layout import safe_path

logger = logging.getLogger(__name__)

_CHUNK: Final = 1024 * 1024
#: Operaciones que leen un fichero subido (no se borra mientras estén en cola o en curso).
BULK_OPERATIONS: Final = ("bulk_preview", "bulk_apply")


def uploads_folder(workspace_dir: Path, owner_id: int, project_id: int) -> Path:
    """Carpeta de subidas del proyecto (solo IDs en la ruta)."""
    return safe_path(workspace_dir, f"users/{int(owner_id)}/projects/{int(project_id)}/uploads")


def upload_file(upload: Upload, settings: Settings) -> Path:
    """Ruta absoluta comprobada del fichero de ``upload``.

    Raises:
        UploadNotFoundError: Ya no está en disco.
    """
    path = safe_path(settings.workspace_dir, upload.path)
    if not path.is_file():
        raise UploadNotFoundError()
    return path


def uploads_bytes(db: Session, user_id: int) -> int:
    """Espacio que ocupan los ficheros subidos por ``user_id`` (cuenta en su cuota)."""
    return int(db.scalar(select(func.coalesce(func.sum(Upload.size_bytes), 0)).where(Upload.user_id == user_id)) or 0)


def save_upload(
    db: Session,
    user: User,
    membership: Membership,
    *,
    filename: str | None,
    stream: BinaryIO,
    settings: Settings,
    ctx: RequestContext,
    used_bytes: int,
) -> Upload:
    """Guarda un fichero subido (editores).

    Args:
        used_bytes: Espacio que ya usa el usuario (ejecuciones + subidas), para la cuota.

    Raises:
        ProjectForbiddenError, UploadTypeError, UploadTooLargeError, UploadContentError, UploadQuotaError.
    """
    if not membership.can("editor"):
        raise ProjectForbiddenError()
    name = display_name(filename)
    kind = kind_for(name)
    limit = settings.upload_max_mb * 1024 * 1024
    quota = settings.user_quota_mb * 1024 * 1024
    project = membership.project
    folder = uploads_folder(settings.workspace_dir, project.owner_id, project.id)
    folder.mkdir(parents=True, exist_ok=True)
    upload_id = new_ulid()
    tmp = folder / f".tmp-{upload_id}"
    digest = hashlib.sha256()
    size = 0
    try:
        with tmp.open("wb") as out:
            while chunk := stream.read(_CHUNK):
                size += len(chunk)
                if size > limit:
                    raise UploadTooLargeError(f"El máximo es {settings.upload_max_mb} MB.")
                if quota and used_bytes + size > quota:
                    raise UploadQuotaError("Purga ejecuciones o ficheros antiguos para liberar espacio.")
                digest.update(chunk)
                out.write(chunk)
        check_content(tmp, kind, max_uncompressed=settings.upload_max_uncompressed_mb * 1024 * 1024)
        final = folder / f"{upload_id}.{kind}"
        tmp.replace(final)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    upload = Upload(
        id=upload_id, project_id=project.id, user_id=user.id, filename=name, kind=kind,
        path=final.relative_to(settings.workspace_dir.resolve()).as_posix(), size_bytes=size,
        sha256=digest.hexdigest(),
    )  # fmt: skip
    db.add(upload)
    audit.record(
        db, action=AuditAction.UPLOAD_CREATE, ctx=ctx, actor_id=user.id, target_type="upload", target_id=upload_id,
        details={"project_id": project.id, "filename": name, "kind": kind, "size_bytes": size},
    )  # fmt: skip
    db.commit()
    return upload


def list_uploads(db: Session, membership: Membership) -> list[Upload]:
    """Ficheros del proyecto, más recientes primero."""
    query = select(Upload).where(Upload.project_id == membership.project.id).order_by(Upload.created_at.desc())
    return list(db.scalars(query).all())


def get_upload(db: Session, membership: Membership, upload_id: str) -> Upload:
    """Fichero del proyecto (404 si es de otro proyecto: no se revela que existe)."""
    upload = db.get(Upload, upload_id)
    if upload is None or upload.project_id != membership.project.id:
        raise UploadNotFoundError()
    return upload


def in_use(db: Session, upload: Upload) -> bool:
    """Lo lee una carga en cola o en curso."""
    runs = db.scalars(
        select(Run).where(
            Run.project_id == upload.project_id,
            Run.operation.in_(BULK_OPERATIONS),
            Run.status.not_in((*TERMINAL_STATUSES, "purged")),
        )
    ).all()
    previews = {run.params.get("preview_run") for run in runs}
    linked = {run.params.get("upload") for run in runs} | {
        p.params.get("upload") for p in db.scalars(select(Run).where(Run.id.in_([x for x in previews if x]))).all()
    }
    return upload.id in linked


def delete_upload(db: Session, user: User, membership: Membership, upload: Upload, *, settings: Settings,
                  ctx: RequestContext) -> None:  # fmt: skip
    """Borra el fichero (editores).

    Raises:
        ProjectForbiddenError: Rol inferior a editor.
        UploadInUseError: Lo usa una carga en cola o en curso.
    """
    if not membership.can("editor"):
        raise ProjectForbiddenError()
    if in_use(db, upload):
        raise UploadInUseError()
    _remove(upload, settings)
    db.delete(upload)
    audit.record(
        db, action=AuditAction.UPLOAD_DELETE, ctx=ctx, actor_id=user.id, target_type="upload", target_id=upload.id,
        details={"project_id": upload.project_id, "filename": upload.filename},
    )  # fmt: skip
    db.commit()


def _remove(upload: Upload, settings: Settings) -> None:
    try:
        safe_path(settings.workspace_dir, upload.path).unlink(missing_ok=True)
    except ValueError:  # ruta guardada fuera del workspace: no se toca nada
        logger.warning("Ruta de subida fuera del workspace", extra={"upload_id": upload.id})


def purge_old_uploads(db: Session, settings: Settings, *, now: datetime | None = None) -> int:
    """Borra los ficheros más antiguos que ``upload_retention_days`` que no use ninguna carga activa."""
    if not settings.upload_retention_days:
        return 0
    limit = (now or utcnow()) - timedelta(days=settings.upload_retention_days)
    old = [u for u in db.scalars(select(Upload).where(Upload.created_at < limit)).all() if not in_use(db, u)]
    for upload in old:
        _remove(upload, settings)
        db.delete(upload)
    db.commit()
    if old:
        logger.info("Subidas purgadas por retención", extra={"purged": len(old)})
    return len(old)
