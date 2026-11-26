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
from app.i18n import Msg
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
    restore_plan,
)
from app.integrations.util_bbdd.progress import RunProgress
from app.jobs.context import JobContext, JobError
from app.jobs.operations.documentation import library_msg

#: Comienzo del ``ValueError`` de ``MigrationPlanner.plan`` cuando el filtro no deja nada (util_bbdd 5.9.0).
NO_MATCH_PREFIX = "Ninguna tabla ni vista del schema"


def _options(params: MigratePlanParams) -> PlannerOptions:
    return PlannerOptions(
        **params.model_dump(include=set(PlannerOptions.__dataclass_fields__)),
    )


def _job_error(exc: Exception) -> JobError:
    if isinstance(exc, JobError):
        return exc
    if isinstance(exc, ValueError) and "no soportado" in str(exc).lower():
        return JobError("invalid_params", Msg("jobs.migrate.engines_unsupported"))
    if isinstance(exc, ValueError) and str(exc).startswith(NO_MATCH_PREFIX):
        # util_bbdd 5.9.0: ``plan(table_filter=...)`` sin ninguna tabla ni vista que case
        return JobError("invalid_params", Msg("jobs.migrate.no_matching_tables"))
    code = classify(exc)
    return JobError(code, library_msg(code, exc))


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


def _recheck(ctx: JobContext, params: MigrateApplyParams) -> tuple[dict[str, Any], dict[str, Any], Any]:
    """Vuelve a comprobar en el worker permiso, rol owner, plan y destino (pudieron cambiar desde que se encoló).

    Returns:
        ``(parámetros del plan, plan.json, migration_plan.json)``.
    """
    with new_session() as db:
        run = db.get(Run, ctx.run_id)
        user = db.get(User, run.user_id) if run and run.user_id else None
        plan_run = db.get(Run, params.plan_run)
        if run is None or user is None or not user.is_active or not user.can("ddl.apply"):
            raise JobError("forbidden", Msg("jobs.no_permission_for", action=Msg("jobs.action.migrate")))
        try:
            membership = get_membership(db, user, ctx.project_id)
        except AppError:
            raise JobError("forbidden", Msg("jobs.not_member")) from None
        if membership.role != "owner":
            raise JobError("forbidden", Msg("jobs.owner_only_for", action=Msg("jobs.action.migrate")))
        if plan_run is None or plan_run.project_id != ctx.project_id:
            raise JobError("invalid_params", Msg("jobs.migrate.plan_gone"))
        try:
            plan = load_plan(db, plan_run, ctx.settings)
            stored = load_stored_plan(db, plan_run, ctx.settings)
        except AppError:
            raise JobError("invalid_params", Msg("jobs.migrate.plan_unavailable")) from None
        if stored is None:  # plan anterior a la 1.3.0
            raise JobError("invalid_params", Msg("jobs.migrate.plan_too_old"))
        try:
            link = get_project_connection(db, run.project, params.target_connection)
        except AppError:
            raise JobError(
                "invalid_params", Msg("jobs.connection_alias_gone", alias=params.target_connection)
            ) from None
        if link.connection.read_only:
            raise JobError("forbidden", Msg("jobs.target_read_only"))
        if link.connection.db_type != plan.get("target_engine"):
            raise JobError("invalid_params", Msg("jobs.target_engine_changed", engine=plan.get("target_engine")))
        return dict(plan_run.params), plan, stored


def _write_report(ctx: JobContext, report: dict[str, Any]) -> None:
    path = ctx.run_dir / REPORT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")


def run_apply(ctx: JobContext) -> None:
    params = MigrateApplyParams.model_validate(ctx.params)
    ctx.progress("preparing", "Comprobando permiso, plan y destino")
    _, plan, stored = _recheck(ctx, params)
    target = ctx.connection_params(params.target_connection)
    verb = "Validando (modo seco)" if params.mode == "dry_run" else "Aplicando"
    ctx.progress("running", f"{verb} {len(plan['statements'])} sentencias en «{params.target_connection}»")
    try:
        migration = restore_plan(stored, plan["statements_hash"])
        progress = (
            RunProgress(
                lambda message, pct: ctx.progress("running", message, pct),
                ctx.cancel_requested,
                ["statements"],
                {"statements": "Sentencias"},
            )
            if params.mode == "apply"
            else None
        )
        report = apply_plan(migration, target, mode=params.mode, outputs_dir=ctx.run_dir / "outputs", progress=progress)
    except PlanOutdatedError:
        raise JobError("plan_changed", Msg("jobs.migrate.plan_outdated")) from None
    except PlanChangedError:
        raise JobError("plan_changed", Msg("jobs.migrate.plan_not_reviewed")) from None
    except PlanBlockedError:
        raise JobError("plan_blocked", Msg("jobs.migrate.plan_blocked")) from None
    except FkTypeMismatchError:
        raise JobError("fk_type_mismatch", Msg("jobs.migrate.fk_type_mismatch")) from None
    except TargetConflictError as exc:
        _write_report(ctx, ApplyReport(params.mode, plan["statements_hash"], 0, conflicts=exc.tables).to_dict())
        raise JobError("target_conflict", Msg("jobs.migrate.target_conflict", tables=", ".join(exc.tables))) from None
    except JobError:
        raise
    except Exception as exc:  # frontera de util_bbdd
        ctx.logger.error("Migración fallida", extra={"exc_type": type(exc).__name__, "mode": params.mode})
        raise _job_error(exc) from None
    _write_report(ctx, report.to_dict())
    ctx.logger.info("Migración", extra={"mode": params.mode, "applied": report.applied, "conflicts": report.conflicts})
    if params.mode == "dry_run" and ctx.cancel_requested():  # el modo seco no escribe: para al terminar
        raise JobError("cancelled", Msg("jobs.cancelled_by_user"))
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
            raise JobError("target_conflict", Msg("jobs.migrate.target_conflict", tables=", ".join(report.conflicts)))
        if report.fk_blocking:
            pairs = ", ".join(
                f"{m['table']}.{m['column']} → {m['ref_table']}.{m['ref_column']}" for m in report.fk_mismatches
            )
            raise JobError("fk_type_mismatch", Msg("jobs.migrate.fk_blocking", pairs=pairs))
        invalid = [v["view"] for v in report.views if v["valid"] is False]
        if invalid:
            raise JobError("view_invalid", Msg("jobs.migrate.view_invalid", views=", ".join(invalid)))
        return
    if report.cancelled:
        raise JobError("cancelled", Msg("jobs.migrate.cancelled", applied=report.applied, statements=report.statements))
    if report.error is not None:
        raise JobError(
            "apply_partial",
            Msg(
                "jobs.migrate.apply_partial",
                position=report.failed_position,
                statements=report.statements,
                applied=report.applied,
                error=report.error,
            ),
        )
