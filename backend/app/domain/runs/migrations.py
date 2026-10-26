"""Migración DDL (Fase 7, ADR-008): plan guardado y reglas para encolar ``migrate_plan`` y ``migrate_apply``.

Escribir en una BD destino exige, **al encolar**:

1. Permiso ``users.can_apply_ddl`` (lo concede un admin) y rol ``owner`` en el proyecto.
2. Un plan ``migrate_plan`` correcto del mismo proyecto, sin avisos ``ERROR`` ni FK entre tipos distintos
   con destino MariaDB/MySQL (``fk_blocking``).
3. Conexión destino del proyecto **no** ``read_only`` y del motor del plan.
4. Para ``apply``: un modo seco (``dry_run``) correcto del mismo plan y destino de hace menos de
   ``DRY_RUN_MAX_AGE``, y ``confirm`` igual al alias del destino.
5. Ninguna otra escritura (migración o volcado) activa sobre ese destino en el proyecto.

El job vuelve a planificar y compara el hash de las sentencias antes de tocar el destino.
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
from app.integrations.util_bbdd.catalog import migration_engines

PLAN_PATH: Final = "outputs/plan/plan.json"
REPORT_PATH: Final = "outputs/plan/report.json"
PLAN_MAX_BYTES: Final = 20 * 1024 * 1024
DRY_RUN_MAX_AGE: Final = timedelta(minutes=60)


class MigrationForbiddenError(AppError):
    status = 403
    title = "No puedes aplicar migraciones en este proyecto"


class PlanNotAvailableError(AppError):
    status = 404
    title = "Esta ejecución no tiene un plan de migración"


class PlanTooLargeError(AppError):
    status = 413
    title = "El plan es demasiado grande para el visor; descarga el script"


def _params_error(field: str, message: str) -> RunParamsError:
    return RunParamsError(message, errors=[{"loc": ["body", "params", field], "msg": message, "type": "value_error"}])


def load_plan(db: Session, run: Run, settings: Settings) -> dict[str, Any]:
    """Plan guardado de una ``migrate_plan`` correcta.

    Raises:
        PlanNotAvailableError: No es un plan correcto, o está purgado.
        PlanTooLargeError: El JSON supera ``PLAN_MAX_BYTES``.
    """
    if run.operation != "migrate_plan" or run.status != "succeeded":
        raise PlanNotAvailableError()
    try:
        artifact, path = get_artifact_by_path(db, run, PLAN_PATH, settings)
    except ArtifactNotFoundError:
        raise PlanNotAvailableError() from None
    if artifact.size_bytes > PLAN_MAX_BYTES:
        raise PlanTooLargeError()
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def can_apply(user: User, membership: Membership) -> bool:
    """Permiso para lanzar ``migrate_apply`` (modo seco o aplicar)."""
    return bool(user.can_apply_ddl) and membership.role == "owner"


def check_plan(db: Session, membership: Membership, params: dict[str, Any]) -> None:
    """``migrate_plan``: el origen es un motor de migración y distinto del destino."""
    link = get_project_connection(db, membership.project, params["source_connection"])
    db_type = link.connection.db_type
    if db_type not in migration_engines()[0]:
        raise _params_error("source_connection", f"util_bbdd no migra desde {db_type}.")
    if db_type == params["target_engine"]:
        raise _params_error("target_engine", "El motor destino debe ser distinto del origen.")


def check_apply(db: Session, user: User, membership: Membership, params: dict[str, Any], settings: Settings) -> None:
    """Reglas de ADR-008 para ``migrate_apply`` (ver la cabecera del módulo).

    Raises:
        MigrationForbiddenError: Sin permiso o sin rol owner (403).
        RunParamsError: Plan, destino, modo seco o confirmación no válidos (422).
        RunStateError: Plan con errores u otra aplicación en curso sobre el destino (409).
    """
    if not user.can_apply_ddl:
        raise MigrationForbiddenError("Necesitas el permiso «Puede aplicar DDL»; pídeselo a un administrador.")
    if membership.role != "owner":
        raise MigrationForbiddenError("Solo el propietario del proyecto puede aplicar migraciones.")
    plan_run = db.get(Run, params["plan_run"])
    if plan_run is None or plan_run.project_id != membership.project.id:
        raise _params_error("plan_run", "El plan no existe en este proyecto.")
    try:
        plan = load_plan(db, plan_run, settings)
    except AppError:
        raise _params_error("plan_run", "La ejecución indicada no es un plan de migración correcto.") from None
    if plan.get("error_count"):
        raise RunStateError("El plan tiene avisos de severidad ERROR: corrígelos y vuelve a planificar.")
    if plan.get("fk_blocking"):
        raise RunStateError("El plan tiene claves foráneas entre tipos distintos que el destino rechazará (G28).")
    alias = params["target_connection"]
    link = get_project_connection(db, membership.project, alias)
    if link.connection.read_only:
        raise _params_error("target_connection", "La conexión destino es de solo lectura.")
    if link.connection.db_type != plan.get("target_engine"):
        raise _params_error("target_connection", f"El plan es para {plan.get('target_engine')}.")
    if params["mode"] == "apply":
        _check_dry_run(db, membership, params)
        if params.get("confirm") != alias:
            raise _params_error("confirm", "Escribe el alias de la conexión destino para confirmar.")
    if active_write(db, membership.project.id, alias):
        raise RunStateError("Ya hay una migración o un volcado en curso sobre esa conexión destino.")


def _check_dry_run(db: Session, membership: Membership, params: dict[str, Any]) -> None:
    dry_id = params.get("dry_run_run")
    dry = db.get(Run, dry_id) if dry_id else None
    valid = (
        dry is not None
        and dry.project_id == membership.project.id
        and dry.operation == "migrate_apply"
        and dry.status == "succeeded"
        and dry.params.get("mode") == "dry_run"
        and dry.params.get("plan_run") == params["plan_run"]
        and dry.params.get("target_connection") == params["target_connection"]
    )
    if not valid or dry is None:
        raise _params_error("dry_run_run", "Aplicar exige un modo seco correcto del mismo plan y destino.")
    if dry.finished_at is None or utcnow() - dry.finished_at > DRY_RUN_MAX_AGE:
        raise _params_error("dry_run_run", "El modo seco tiene más de 60 minutos: repítelo.")
