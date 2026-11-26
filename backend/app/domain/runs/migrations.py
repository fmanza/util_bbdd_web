"""Migración DDL (Fase 7, ADR-008): plan guardado y reglas para encolar ``migrate_plan`` y ``migrate_apply``.

Escribir en una BD destino exige, **al encolar**:

1. Permiso ``ddl.apply`` del rol (ADR-014) y rol ``owner`` en el proyecto.
2. Un plan ``migrate_plan`` correcto del mismo proyecto, sin avisos ``ERROR`` ni FK entre tipos distintos
   con destino MariaDB/MySQL (``fk_blocking``).
3. Conexión destino del proyecto **no** ``read_only`` y del motor del plan.
4. Para ``apply``: un modo seco (``dry_run``) correcto del mismo plan y destino de hace menos de
   ``DRY_RUN_MAX_AGE``, y ``confirm`` igual al alias del destino.
5. Ninguna otra escritura (migración o volcado) activa sobre ese destino en el proyecto.

El job reconstruye el plan revisado (``migration_plan.json``, util_bbdd 4.3.0) o, si es anterior a la 1.3.0, vuelve a
planificar, y en los dos casos compara el hash de las sentencias antes de tocar el destino.
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
from app.domain.runs.errors import ArtifactNotFoundError, RunStateError
from app.domain.runs.service import get_artifact_by_path
from app.domain.runs.targets import check_confirm, check_no_write, check_target, check_writer, params_error
from app.i18n import Msg
from app.integrations.util_bbdd.catalog import migration_engines

PLAN_PATH: Final = "outputs/plan/plan.json"
#: ``MigrationPlan.to_dict()`` (util_bbdd 4.3.0, GAPS G26); no existe en los planes anteriores a la 1.3.0.
UTIL_BBDD_PLAN_PATH: Final = "outputs/plan/migration_plan.json"
REPORT_PATH: Final = "outputs/plan/report.json"
PLAN_MAX_BYTES: Final = 20 * 1024 * 1024
DRY_RUN_MAX_AGE: Final = timedelta(minutes=60)


class MigrationForbiddenError(AppError):
    status = 403


class PlanNotAvailableError(AppError):
    status = 404


class PlanTooLargeError(AppError):
    status = 413


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


def load_stored_plan(db: Session, run: Run, settings: Settings) -> Any | None:
    """``MigrationPlan.to_dict()`` guardado por la ``migrate_plan``; ``None`` si el plan es anterior a la 1.3.0.

    Raises:
        PlanTooLargeError: El JSON supera ``PLAN_MAX_BYTES``.
    """
    try:
        artifact, path = get_artifact_by_path(db, run, UTIL_BBDD_PLAN_PATH, settings)
    except ArtifactNotFoundError:
        return None
    if artifact.size_bytes > PLAN_MAX_BYTES:
        raise PlanTooLargeError()
    return json.loads(path.read_text(encoding="utf-8"))


def can_apply(user: User, membership: Membership) -> bool:
    """Permiso para lanzar ``migrate_apply`` (modo seco o aplicar)."""
    return user.can("ddl.apply") and membership.role == "owner"


def check_plan(db: Session, membership: Membership, params: dict[str, Any]) -> None:
    """``migrate_plan``: el origen es un motor de migración y distinto del destino."""
    link = get_project_connection(db, membership.project, params["source_connection"])
    db_type = link.connection.db_type
    if db_type not in migration_engines()[0]:
        raise params_error("source_connection", Msg("runs.migrate.source_unsupported", engine=db_type))
    if db_type == params["target_engine"]:
        raise params_error("target_engine", Msg("runs.migrate.same_engine"))


def check_apply(db: Session, user: User, membership: Membership, params: dict[str, Any], settings: Settings) -> None:
    """Reglas de ADR-008 para ``migrate_apply`` (ver la cabecera del módulo).

    Raises:
        MigrationForbiddenError: Sin permiso o sin rol owner (403).
        RunParamsError: Plan, destino, modo seco o confirmación no válidos (422).
        RunStateError: Plan con errores u otra aplicación en curso sobre el destino (409).
    """
    check_writer(
        user,
        membership,
        permission="ddl.apply",
        error=MigrationForbiddenError,
        owner_only=Msg("runs.migrate.owner_only"),
    )
    plan_run = db.get(Run, params["plan_run"])
    if plan_run is None or plan_run.project_id != membership.project.id:
        raise params_error("plan_run", Msg("runs.migrate.plan_missing"))
    try:
        plan = load_plan(db, plan_run, settings)
    except AppError:
        raise params_error("plan_run", Msg("runs.migrate.plan_invalid")) from None
    if plan.get("error_count"):
        raise RunStateError(Msg("runs.migrate.plan_errors"))
    if plan.get("fk_blocking"):
        raise RunStateError(Msg("runs.migrate.fk_blocking"))
    alias = params["target_connection"]
    check_target(
        get_project_connection(db, membership.project, alias),
        plan.get("target_engine"),
        field="target_connection",
        engine_msg=Msg("runs.migrate.plan_other_engine", engine=str(plan.get("target_engine"))),
    )
    if params["mode"] == "apply":
        _check_dry_run(db, membership, params)
        check_confirm(params, alias)
    check_no_write(db, membership.project.id, alias, Msg("runs.migrate.write_in_progress"))


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
        raise params_error("dry_run_run", Msg("runs.migrate.dry_run_required"))
    if dry.finished_at is None or utcnow() - dry.finished_at > DRY_RUN_MAX_AGE:
        raise params_error("dry_run_run", Msg("runs.migrate.dry_run_expired"))
