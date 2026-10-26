"""``migrate_plan`` y ``migrate_apply``: migración DDL de util_bbdd como ejecuciones (Fase 7, ADR-008)."""

from __future__ import annotations

import json
from typing import Any

from app.core.errors import AppError
from app.db.models import Run, User
from app.db.session import new_session
from app.domain.projects.service import get_membership, get_project_connection
from app.domain.runs.migrations import REPORT_PATH, load_plan, load_stored_plan
from app.domain.runs.operations import MigrateApplyParams, MigratePlanParams
from app.integrations.util_bbdd.isolated import classify
from app.integrations.util_bbdd.migrate import (
    ApplyReport,
    FkTypeMismatchError,
    PlanBlockedError,
    PlanChangedError,
    PlannerOptions,
    PlanOutdatedError,
    TargetConflictError,
    apply_plan,
    create_plan,
    replan,
    restore_plan,
)
from app.jobs.context import JobContext, JobError
from app.jobs.operations.documentation import _MESSAGES


def _options(params: MigratePlanParams) -> PlannerOptions:
    return PlannerOptions(
        **params.model_dump(include=set(PlannerOptions.__dataclass_fields__)),
    )


def _job_error(exc: Exception) -> JobError:
    if isinstance(exc, JobError):
        return exc
    if isinstance(exc, ValueError) and "no soportado" in str(exc).lower():
        return JobError("invalid_params", "Combinación de motores no soportada por util_bbdd.")
    code = classify(exc)
    return JobError(code, _MESSAGES.get(code, f"util_bbdd falló ({type(exc).__name__})."))


def run_plan(ctx: JobContext) -> None:
    params = MigratePlanParams.model_validate(ctx.params)
    ctx.progress("connecting", f"Leyendo el origen «{params.source_connection}»")
    db_type, conn_params = ctx.connection_params(params.source_connection)
    ctx.progress("running", f"Planificando la migración {db_type} → {params.target_engine}")
    try:
        summary = create_plan(
            db_type,
            conn_params,
            schema=params.source_schema,
            target_engine=params.target_engine,
            options=_options(params),
            outputs_dir=ctx.run_dir / "outputs",
        )
    except Exception as exc:  # frontera de util_bbdd: el log solo lleva el tipo
        ctx.logger.error("Plan fallido", extra={"exc_type": type(exc).__name__})
        raise _job_error(exc) from None
    ctx.logger.info("Plan generado", extra=summary)
    blocked = f"; {summary['errors']} errores impiden aplicarlo" if summary["errors"] else ""
    ctx.progress(
        "reporting", f"{summary['tables']} tablas, {summary['statements']} sentencias, {summary['warnings']} avisos"
        f"{blocked}", 100,
    )  # fmt: skip


def _recheck(ctx: JobContext, params: MigrateApplyParams) -> tuple[dict[str, Any], dict[str, Any], Any | None]:
    """Vuelve a comprobar en el worker permiso, rol owner, plan y destino (pudieron cambiar desde que se encoló).

    Returns:
        ``(parámetros del plan, plan.json, migration_plan.json o None si el plan es anterior a la 1.3.0)``.
    """
    with new_session() as db:
        run = db.get(Run, ctx.run_id)
        user = db.get(User, run.user_id) if run and run.user_id else None
        plan_run = db.get(Run, params.plan_run)
        if run is None or user is None or not user.is_active or not user.can_apply_ddl:
            raise JobError("forbidden", "El usuario ya no tiene permiso para aplicar migraciones.")
        try:
            membership = get_membership(db, user, ctx.project_id)
        except AppError:
            raise JobError("forbidden", "El usuario ya no es miembro del proyecto.") from None
        if membership.role != "owner":
            raise JobError("forbidden", "Solo el propietario del proyecto puede aplicar migraciones.")
        if plan_run is None or plan_run.project_id != ctx.project_id:
            raise JobError("invalid_params", "El plan ya no existe.")
        try:
            plan = load_plan(db, plan_run, ctx.settings)
            stored = load_stored_plan(db, plan_run, ctx.settings)
        except AppError:
            raise JobError("invalid_params", "El plan ya no está disponible (¿purgado?).") from None
        try:
            link = get_project_connection(db, run.project, params.target_connection)
        except AppError:
            raise JobError(
                "invalid_params", f"El proyecto ya no tiene la conexión «{params.target_connection}»."
            ) from None
        if link.connection.read_only:
            raise JobError("forbidden", "La conexión destino es de solo lectura.")
        if link.connection.db_type != plan.get("target_engine"):
            raise JobError("invalid_params", f"La conexión destino ya no es {plan.get('target_engine')}.")
        return dict(plan_run.params), plan, stored


def _write_report(ctx: JobContext, report: dict[str, Any]) -> None:
    path = ctx.run_dir / REPORT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")


def run_apply(ctx: JobContext) -> None:
    params = MigrateApplyParams.model_validate(ctx.params)
    ctx.progress("preparing", "Comprobando permiso, plan y destino")
    plan_params, plan, stored = _recheck(ctx, params)
    plan_model = MigratePlanParams.model_validate(plan_params)
    target = ctx.connection_params(params.target_connection)
    verb = "Validando (modo seco)" if params.mode == "dry_run" else "Aplicando"
    ctx.progress("running", f"{verb} {len(plan['statements'])} sentencias en «{params.target_connection}»")
    try:
        if stored is not None:
            migration = restore_plan(stored, plan["statements_hash"])
        else:  # plan anterior a la 1.3.0: se replanifica contra el origen (ADR-008)
            migration = replan(
                ctx.connection_params(plan_model.source_connection),
                plan["target_engine"],
                schema=plan["source_schema"],
                options=_options(plan_model),
                expected_hash=plan["statements_hash"],
            )
        report = apply_plan(migration, target, mode=params.mode, outputs_dir=ctx.run_dir / "outputs")
    except PlanOutdatedError:
        raise JobError(
            "plan_changed", "El plan se generó con otra versión de util_bbdd o está dañado: vuelve a planificar."
        ) from None
    except PlanChangedError:
        changed = "El origen ha cambiado desde el plan" if stored is None else "El plan guardado no es el revisado"
        raise JobError("plan_changed", f"{changed}: vuelve a planificar.") from None
    except PlanBlockedError:
        raise JobError("plan_blocked", "El plan tiene avisos de severidad ERROR.") from None
    except FkTypeMismatchError:
        raise JobError("fk_type_mismatch", "El plan tiene claves foráneas entre tipos distintos.") from None
    except TargetConflictError as exc:
        _write_report(ctx, ApplyReport(params.mode, plan["statements_hash"], 0, conflicts=exc.tables).to_dict())
        raise JobError(
            "target_conflict", f"El destino ya tiene tablas o vistas del plan: {', '.join(exc.tables)}."
        ) from None
    except JobError:
        raise
    except Exception as exc:  # frontera de util_bbdd
        ctx.logger.error("Migración fallida", extra={"exc_type": type(exc).__name__, "mode": params.mode})
        raise _job_error(exc) from None
    _write_report(ctx, report.to_dict())
    ctx.logger.info("Migración", extra={"mode": params.mode, "applied": report.applied, "conflicts": report.conflicts})
    _raise_for_report(report)
    message = (
        f"Modo seco correcto: {report.statements} sentencias listas para aplicar"
        if params.mode == "dry_run"
        else f"{report.applied} sentencias aplicadas"
    )
    ctx.progress("reporting", message, 100)


def _raise_for_report(report: ApplyReport) -> None:
    """Convierte en fallo lo que impide aplicar (modo seco) o lo que falló a medias (aplicar)."""
    if report.mode == "dry_run":
        if report.conflicts:
            raise JobError(
                "target_conflict", f"El destino ya tiene tablas o vistas del plan: {', '.join(report.conflicts)}."
            )
        if report.fk_blocking:
            pairs = ", ".join(
                f"{m['table']}.{m['column']} → {m['ref_table']}.{m['ref_column']}" for m in report.fk_mismatches
            )
            raise JobError(
                "fk_type_mismatch", f"Claves foráneas entre tipos distintos (el destino las rechazará): {pairs}."
            )
        invalid = [v["view"] for v in report.views if v["valid"] is False]
        if invalid:
            raise JobError("view_invalid", f"Vistas que no se pueden crear en el destino: {', '.join(invalid)}.")
        return
    if report.error is not None:
        raise JobError(
            "apply_partial",
            f"Falló la sentencia {report.failed_position}/{report.statements}; quedaron aplicadas {report.applied}. "
            f"Motor: {report.error}",
        )
