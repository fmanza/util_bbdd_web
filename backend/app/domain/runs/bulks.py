"""Carga bulk desde fichero (Fase 9, ADR-010): reglas para encolar ``bulk_preview`` y ``bulk_apply``.

``bulk_preview`` (modo seco) solo lee: exige que el fichero sea **del mismo proyecto**. Escribir filas exige, **al
encolar** (y de nuevo en el worker):

1. Permiso ``data.write`` del rol (ADR-014) y rol ``owner``.
2. Una ``bulk_preview`` correcta del mismo proyecto de hace menos de ``PREVIEW_MAX_AGE`` y **sin errores de
   validación**: la carga usa sus parámetros.
3. El mismo fichero (SHA-256) y la misma conexión destino (id), no ``read_only`` y del mismo motor.
4. ``confirm`` = alias del destino; en update/delete, ``confirm_rows`` = filas afectadas de la vista previa; si el
   plan no es atómico (``ParallelPlan.atomic``, G36), ``accept_non_atomic``. Sin ella, la carga pide a util_bbdd
   ``require_atomic`` (un hilo).
5. Ninguna otra escritura activa sobre ese destino (``targets.active_write``).
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Final

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import Project, Run, Upload, User
from app.domain.projects.service import Membership, get_project_connection
from app.domain.runs.errors import ArtifactNotFoundError, RunStateError
from app.domain.runs.service import get_artifact_by_path
from app.domain.runs.targets import (
    check_confirm,
    check_no_write,
    check_target,
    check_writer,
    load_fresh_preview,
    params_error,
)
from app.i18n import Msg

PREVIEW_PATH: Final = "outputs/bulk/preview.json"
RESULT_PATH: Final = "outputs/bulk/result.json"
JSON_MAX_BYTES: Final = 20 * 1024 * 1024
PREVIEW_MAX_AGE: Final = timedelta(minutes=60)


class BulkForbiddenError(AppError):
    status = 403


class BulkNotAvailableError(AppError):
    status = 404


def _load(db: Session, run: Run, path: str, settings: Settings) -> dict[str, Any]:
    try:
        artifact, file = get_artifact_by_path(db, run, path, settings)
    except ArtifactNotFoundError:
        raise BulkNotAvailableError() from None
    if artifact.size_bytes > JSON_MAX_BYTES:
        raise BulkNotAvailableError(Msg("runs.document_too_large"))
    data: dict[str, Any] = json.loads(file.read_text(encoding="utf-8"))
    return data


def load_preview(db: Session, run: Run, settings: Settings) -> dict[str, Any]:
    """Vista previa de una ``bulk_preview`` correcta."""
    if run.operation != "bulk_preview" or run.status != "succeeded":
        raise BulkNotAvailableError()
    return _load(db, run, PREVIEW_PATH, settings)


def load_result(db: Session, run: Run, settings: Settings) -> dict[str, Any]:
    """Resultado de un ``bulk_apply`` terminado."""
    if run.operation != "bulk_apply":
        raise BulkNotAvailableError()
    return _load(db, run, RESULT_PATH, settings)


def project_upload(db: Session, project: Project, upload_id: str) -> Upload | None:
    """Fichero del proyecto (``None`` si no existe o es de otro proyecto)."""
    upload = db.get(Upload, upload_id)
    return upload if upload is not None and upload.project_id == project.id else None


def check_preview(db: Session, membership: Membership, params: dict[str, Any]) -> None:
    """``bulk_preview``: el fichero es de este proyecto."""
    if project_upload(db, membership.project, params["upload"]) is None:
        raise params_error("upload", Msg("runs.bulk.upload_missing"))


def target_changed(
    db: Session, project: Project, preview_params: dict[str, Any], preview: dict[str, Any]
) -> Msg | None:
    """Motivo por el que la conexión destino o el fichero ya no son los de la vista previa (``None`` si lo son)."""
    alias = str(preview_params["target_connection"])
    try:
        link = get_project_connection(db, project, alias)
    except AppError:
        return Msg("runs.connection_gone", alias=alias)
    if link.connection_id != preview.get("target_connection_id"):
        return Msg("runs.connection_replaced", alias=alias)
    upload = project_upload(db, project, str(preview_params["upload"]))
    if upload is None or upload.sha256 != preview.get("upload_sha256"):
        return Msg("runs.bulk.upload_changed")
    return None


def check_apply(db: Session, user: User, membership: Membership, params: dict[str, Any], settings: Settings) -> None:
    """Reglas de ADR-010 para ``bulk_apply`` (ver la cabecera del módulo).

    Raises:
        BulkForbiddenError: Sin permiso o sin rol owner (403).
        RunParamsError: Vista previa, destino, fichero o confirmaciones no válidos (422).
        RunStateError: La vista previa tiene errores u otra escritura está en curso sobre el destino (409).
    """
    check_writer(
        user, membership, permission="data.write", error=BulkForbiddenError, owner_only=Msg("runs.bulk.owner_only")
    )
    preview_run, preview = load_fresh_preview(
        db, membership, params, settings, load=load_preview, max_age=PREVIEW_MAX_AGE
    )
    if preview.get("errors"):
        raise RunStateError(Msg("runs.bulk.preview_has_errors"))
    changed = target_changed(db, membership.project, preview_run.params, preview)
    if changed:
        raise params_error("preview_run", changed)
    alias = str(preview_run.params["target_connection"])
    check_target(
        get_project_connection(db, membership.project, alias),
        preview.get("target_engine"),
        field="preview_run",
        engine_msg=Msg("runs.target_engine_changed", engine=str(preview.get("target_engine"))),
    )
    check_confirm(params, alias)
    if preview.get("operation") in {"update", "delete"} and params.get("confirm_rows") != preview.get("matches"):
        raise params_error("confirm_rows", Msg("runs.bulk.confirm_rows"))
    if not plan_atomic(preview) and not params.get("accept_non_atomic"):
        raise params_error("accept_non_atomic", Msg("runs.bulk.accept_non_atomic"))
    check_no_write(db, membership.project.id, alias, Msg("runs.write_in_progress"))


def plan_atomic(preview: dict[str, Any]) -> bool:
    """Si la carga de la vista previa irá en una sola transacción (``ParallelPlan.atomic``, util_bbdd 4.5.0, G36).

    Las vistas previas anteriores a la 1.5.0 no lo guardan: entonces, atómica con un solo hilo.
    """
    plan = preview.get("parallel") or {}
    atomic = plan.get("atomic")
    return bool(atomic) if isinstance(atomic, bool) else plan.get("workers", 1) <= 1
