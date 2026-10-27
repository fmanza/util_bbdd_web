"""Carga bulk desde fichero (Fase 9, ADR-010): reglas para encolar ``bulk_preview`` y ``bulk_apply``.

``bulk_preview`` (modo seco) solo lee: exige que el fichero sea **del mismo proyecto**. Escribir filas exige, **al
encolar** (y de nuevo en el worker):

1. Permiso ``users.can_write_data`` y rol ``owner``.
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
from app.db.models import Project, Run, Upload, User, utcnow
from app.domain.projects.service import Membership, get_project_connection
from app.domain.runs.errors import ArtifactNotFoundError, RunParamsError, RunStateError
from app.domain.runs.service import get_artifact_by_path
from app.domain.runs.targets import active_write

PREVIEW_PATH: Final = "outputs/bulk/preview.json"
RESULT_PATH: Final = "outputs/bulk/result.json"
JSON_MAX_BYTES: Final = 20 * 1024 * 1024
PREVIEW_MAX_AGE: Final = timedelta(minutes=60)


class BulkForbiddenError(AppError):
    status = 403
    title = "No puedes cargar datos en este proyecto"


class BulkNotAvailableError(AppError):
    status = 404
    title = "Esta ejecución no tiene una vista previa o un resultado de carga"


def _params_error(field: str, message: str) -> RunParamsError:
    return RunParamsError(message, errors=[{"loc": ["body", "params", field], "msg": message, "type": "value_error"}])


def _load(db: Session, run: Run, path: str, settings: Settings) -> dict[str, Any]:
    try:
        artifact, file = get_artifact_by_path(db, run, path, settings)
    except ArtifactNotFoundError:
        raise BulkNotAvailableError() from None
    if artifact.size_bytes > JSON_MAX_BYTES:
        raise BulkNotAvailableError("El documento es demasiado grande para el visor.")
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
        raise _params_error("upload", "El fichero no existe en este proyecto.")


def target_changed(
    db: Session, project: Project, preview_params: dict[str, Any], preview: dict[str, Any]
) -> str | None:
    """Motivo por el que la conexión destino o el fichero ya no son los de la vista previa (``None`` si lo son)."""
    alias = str(preview_params["target_connection"])
    try:
        link = get_project_connection(db, project, alias)
    except AppError:
        return f"El proyecto ya no tiene la conexión «{alias}»."
    if link.connection_id != preview.get("target_connection_id"):
        return f"La conexión «{alias}» ya no es la de la vista previa: repítela."
    upload = project_upload(db, project, str(preview_params["upload"]))
    if upload is None or upload.sha256 != preview.get("upload_sha256"):
        return "El fichero de la vista previa ya no está o ha cambiado."
    return None


def check_apply(db: Session, user: User, membership: Membership, params: dict[str, Any], settings: Settings) -> None:
    """Reglas de ADR-010 para ``bulk_apply`` (ver la cabecera del módulo).

    Raises:
        BulkForbiddenError: Sin permiso o sin rol owner (403).
        RunParamsError: Vista previa, destino, fichero o confirmaciones no válidos (422).
        RunStateError: La vista previa tiene errores u otra escritura está en curso sobre el destino (409).
    """
    if not user.can_write_data:
        raise BulkForbiddenError("Necesitas el permiso «Puede escribir datos»; pídeselo a un administrador.")
    if membership.role != "owner":
        raise BulkForbiddenError("Solo el propietario del proyecto puede cargar datos.")
    preview_run = db.get(Run, params["preview_run"])
    if preview_run is None or preview_run.project_id != membership.project.id:
        raise _params_error("preview_run", "La vista previa no existe en este proyecto.")
    try:
        preview = load_preview(db, preview_run, settings)
    except AppError:
        raise _params_error("preview_run", "La ejecución indicada no es una vista previa correcta.") from None
    if preview_run.finished_at is None or utcnow() - preview_run.finished_at > PREVIEW_MAX_AGE:
        raise _params_error("preview_run", "La vista previa tiene más de 60 minutos: repítela.")
    if preview.get("errors"):
        raise RunStateError("La vista previa tiene errores de validación: corrígelos y repítela.")
    changed = target_changed(db, membership.project, preview_run.params, preview)
    if changed:
        raise _params_error("preview_run", changed)
    alias = str(preview_run.params["target_connection"])
    link = get_project_connection(db, membership.project, alias)
    if link.connection.read_only:
        raise _params_error("preview_run", "La conexión destino es de solo lectura.")
    if link.connection.db_type != preview.get("target_engine"):
        raise _params_error("preview_run", f"La conexión destino ya no es {preview.get('target_engine')}.")
    if params.get("confirm") != alias:
        raise _params_error("confirm", "Escribe el alias de la conexión destino para confirmar.")
    if preview.get("operation") in {"update", "delete"} and params.get("confirm_rows") != preview.get("matches"):
        raise _params_error("confirm_rows", "Escribe el número de filas afectadas que indica la vista previa.")
    if not plan_atomic(preview) and not params.get("accept_non_atomic"):
        raise _params_error("accept_non_atomic", "La carga paralela no es atómica: acéptalo para continuar.")
    if active_write(db, membership.project.id, alias):
        raise RunStateError("Ya hay una escritura en curso sobre esa conexión destino.")


def plan_atomic(preview: dict[str, Any]) -> bool:
    """Si la carga de la vista previa irá en una sola transacción (``ParallelPlan.atomic``, util_bbdd 4.5.0, G36).

    Las vistas previas anteriores a la 1.5.0 no lo guardan: entonces, atómica con un solo hilo.
    """
    plan = preview.get("parallel") or {}
    atomic = plan.get("atomic")
    return bool(atomic) if isinstance(atomic, bool) else plan.get("workers", 1) <= 1
