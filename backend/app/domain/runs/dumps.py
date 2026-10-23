"""Volcado de datos (Fase 8, ADR-009): vista previa guardada y reglas para encolar ``dump_apply``.

``dump_preview`` es el modo seco (solo lee). Escribir filas en la BD destino exige, **al encolar**:

1. Permiso ``users.can_write_data`` (lo concede un admin) y rol ``owner`` en el proyecto.
2. Una ``dump_preview`` correcta del mismo proyecto de hace menos de ``PREVIEW_MAX_AGE``: el volcado usa **sus**
   parámetros (no se pueden cambiar entre la revisión y la ejecución).
3. Las conexiones de la vista previa siguen en el proyecto con el **mismo id** (un alias reasignado a otra
   conexión no vale), el destino **no** ``read_only`` y del mismo motor.
4. ``confirm`` igual al alias del destino y, si la vista previa vacía el destino, ``confirm_truncate`` = «VACIAR».
5. Ninguna otra escritura (volcado o migración) activa sobre ese destino en el proyecto.

El job vuelve a comprobarlo y exige la misma estructura (``structure_hash``) antes de escribir.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Final

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import Run, User, utcnow
from app.domain.projects.service import Membership, get_project_connection
from app.domain.runs.errors import ArtifactNotFoundError, RunParamsError, RunStateError
from app.domain.runs.service import get_artifact_by_path
from app.domain.runs.targets import active_write

PREVIEW_PATH: Final = "outputs/dump/preview.json"
RESULT_PATH: Final = "outputs/dump/result.json"
JSON_MAX_BYTES: Final = 20 * 1024 * 1024
PREVIEW_MAX_AGE: Final = timedelta(minutes=60)
TRUNCATE_WORD: Final = "VACIAR"


class DumpForbiddenError(AppError):
    status = 403
    title = "No puedes volcar datos en este proyecto"


class DumpNotAvailableError(AppError):
    status = 404
    title = "Esta ejecución no tiene una vista previa o un resultado de volcado"


class DumpTooLargeError(AppError):
    status = 413
    title = "El documento es demasiado grande para el visor; descarga el informe"


def _params_error(field: str, message: str) -> RunParamsError:
    return RunParamsError(message, errors=[{"loc": ["body", "params", field], "msg": message, "type": "value_error"}])


def _load(db: Session, run: Run, path: str, settings: Settings) -> dict[str, Any]:
    try:
        artifact, file = get_artifact_by_path(db, run, path, settings)
    except ArtifactNotFoundError:
        raise DumpNotAvailableError() from None
    if artifact.size_bytes > JSON_MAX_BYTES:
        raise DumpTooLargeError()
    data: dict[str, Any] = json.loads(file.read_text(encoding="utf-8"))
    return data


def load_preview(db: Session, run: Run, settings: Settings) -> dict[str, Any]:
    """Vista previa de una ``dump_preview`` correcta.

    Raises:
        DumpNotAvailableError: No es una vista previa correcta, o está purgada.
    """
    if run.operation != "dump_preview" or run.status != "succeeded":
        raise DumpNotAvailableError()
    return _load(db, run, PREVIEW_PATH, settings)


def load_result(db: Session, run: Run, settings: Settings) -> dict[str, Any]:
    """Resultado de un ``dump_apply`` terminado (también si falló a medias)."""
    if run.operation != "dump_apply":
        raise DumpNotAvailableError()
    return _load(db, run, RESULT_PATH, settings)


def check_apply(db: Session, user: User, membership: Membership, params: dict[str, Any], settings: Settings) -> None:
    """Reglas de ADR-009 para ``dump_apply`` (ver la cabecera del módulo).

    Raises:
        DumpForbiddenError: Sin permiso o sin rol owner (403).
        RunParamsError: Vista previa, destino o confirmaciones no válidos (422).
        RunStateError: Otro volcado en curso sobre el destino (409).
    """
    if not user.can_write_data:
        raise DumpForbiddenError("Necesitas el permiso «Puede escribir datos»; pídeselo a un administrador.")
    if membership.role != "owner":
        raise DumpForbiddenError("Solo el propietario del proyecto puede volcar datos.")
    preview_run = db.get(Run, params["preview_run"])
    if preview_run is None or preview_run.project_id != membership.project.id:
        raise _params_error("preview_run", "La vista previa no existe en este proyecto.")
    try:
        preview = load_preview(db, preview_run, settings)
    except AppError:
        raise _params_error("preview_run", "La ejecución indicada no es una vista previa correcta.") from None
    if preview_run.finished_at is None or utcnow() - preview_run.finished_at > PREVIEW_MAX_AGE:
        raise _params_error("preview_run", "La vista previa tiene más de 60 minutos: repítela.")
    alias = str(preview_run.params["target_connection"])
    changed = connections_changed(db, membership.project, preview_run.params, preview)
    if changed:
        raise _params_error("preview_run", changed)
    link = get_project_connection(db, membership.project, alias)
    if link.connection.read_only:
        raise _params_error("preview_run", "La conexión destino es de solo lectura.")
    if link.connection.db_type != preview.get("target_engine"):
        raise _params_error("preview_run", f"La conexión destino ya no es {preview.get('target_engine')}.")
    if params.get("confirm") != alias:
        raise _params_error("confirm", "Escribe el alias de la conexión destino para confirmar.")
    if preview.get("truncate_target") and params.get("confirm_truncate") != TRUNCATE_WORD:
        raise _params_error("confirm_truncate", f"Escribe «{TRUNCATE_WORD}» para confirmar que se vacía el destino.")
    if active_write(db, membership.project.id, alias):
        raise RunStateError("Ya hay un volcado o una migración en curso sobre esa conexión destino.")


def connections_changed(db: Session, project: Any, params: dict[str, Any], preview: dict[str, Any]) -> str | None:
    """Motivo por el que las conexiones ya no son las de la vista previa (``None`` si siguen siendo las mismas).

    La vista previa guarda el id de cada conexión: un alias quitado y asociado a otra conexión del mismo motor y con
    las mismas tablas daría la misma huella de estructura y escribiría en una BD que no se revisó.
    """
    for side in ("source", "target"):
        alias = str(params[f"{side}_connection"])
        try:
            link = get_project_connection(db, project, alias)
        except AppError:
            return f"El proyecto ya no tiene la conexión «{alias}»."
        if link.connection_id != preview.get(f"{side}_connection_id"):
            return f"La conexión «{alias}» ya no es la de la vista previa: repítela."
    return None
