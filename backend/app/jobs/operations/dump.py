"""``dump_preview``, ``dump_apply`` y ``dump_restore``: volcado de datos de util_bbdd como ejecuciones (Fase 8,
ADR-009)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import Run, User
from app.db.session import new_session
from app.domain.projects.service import get_membership, get_project_connection
from app.domain.runs.dumps import PREVIEW_PATH, RESULT_PATH, connections_changed, load_preview, restore_target
from app.domain.runs.operations import DumpApplyParams, DumpPreviewParams, DumpRestoreParams
from app.domain.runs.service import DUMP_JOURNAL_PATH, DUMP_TARGET_PATH
from app.i18n import Msg
from app.integrations.util_bbdd.compare import SchemaNotFoundError
from app.integrations.util_bbdd.dump import (
    DumpOptions,
    DumpProgress,
    Endpoint,
    NoMatchingTablesError,
    PreviewChangedError,
    UnknownTablesError,
    build_preview,
    parse_tables,
    restore_constraints,
    run_dump,
)
from app.integrations.util_bbdd.isolated import classify
from app.jobs.context import JobContext, JobError
from app.jobs.operations.documentation import library_msg, msg_list

RESTORE_PATH: Final = "outputs/dump/restore.json"


def _options(params: DumpPreviewParams) -> DumpOptions:
    return DumpOptions(
        tables=parse_tables(params.tables),
        table_include=params.table_include,
        table_exclude=params.table_exclude,
        truncate_target=params.truncate_target,
        on_error=params.on_error,
        max_rejects=params.max_rejects,
        chunk_size=params.chunk_size,
        max_parallel_tables=params.max_parallel_tables,
        manage_indexes=params.manage_indexes,
        sync_pk_sequences=params.sync_pk_sequences,
        locale=params.locale,
    )


def _endpoints(ctx: JobContext, params: DumpPreviewParams) -> tuple[Endpoint, Endpoint]:
    source = ctx.connection_params(params.source_connection)
    target = ctx.connection_params(params.target_connection)
    return Endpoint(*source, params.source_schema), Endpoint(*target, params.target_schema)


def _job_error(exc: Exception) -> JobError:
    if isinstance(exc, JobError):
        return exc
    if isinstance(exc, NoMatchingTablesError):
        return JobError("invalid_params", Msg("jobs.dump.no_matching_tables"))
    if isinstance(exc, SchemaNotFoundError):
        return JobError("invalid_params", exc.msg)
    if isinstance(exc, UnknownTablesError):
        return JobError("invalid_params", Msg("jobs.dump.unknown_tables", tables=", ".join(exc.tables)))
    code = classify(exc)
    return JobError(code, library_msg(code, exc))


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def run_preview(ctx: JobContext) -> None:
    params = DumpPreviewParams.model_validate(ctx.params)
    ctx.progress("connecting", "Preparando las conexiones")
    source, target = _endpoints(ctx, params)
    ctx.progress("running", "Analizando tablas, orden de carga y filas")
    try:
        preview = build_preview(source, target, _options(params))
    except Exception as exc:  # frontera de util_bbdd/SQLAlchemy: el log solo lleva el tipo
        ctx.logger.error("Vista previa fallida", extra={"exc_type": type(exc).__name__})
        raise _job_error(exc) from None
    preview.update(_connection_ids(ctx, params))
    _write(ctx.run_dir / PREVIEW_PATH, preview)
    tables = preview["tables"]
    missing = sum(1 for t in tables if t["target_table"] is None)
    rows = sum(t["source_rows"] for t in tables)
    ctx.logger.info("Vista previa del volcado", extra={"tables": len(tables), "missing": missing, "rows": rows})
    ctx.progress("reporting", f"{len(tables)} tablas ({missing} sin destino), {rows} filas en el origen", 100)


def _connection_ids(ctx: JobContext, params: DumpPreviewParams) -> dict[str, int]:
    """Id de las conexiones de la vista previa: el volcado exige que los alias sigan apuntando a ellas."""
    with new_session() as db:
        run = db.get(Run, ctx.run_id)
        if run is None:
            raise JobError("invalid_params", Msg("jobs.run_gone"))
        return {
            f"{side}_connection_id": get_project_connection(db, run.project, alias).connection_id
            for side, alias in (("source", params.source_connection), ("target", params.target_connection))
        }


def _check_writer(db: Session, ctx: JobContext, action: Msg) -> Run:
    """Permiso ``data.write`` y rol owner del usuario del run (pudieron cambiar desde que se encoló)."""
    run = db.get(Run, ctx.run_id)
    user = db.get(User, run.user_id) if run and run.user_id else None
    if run is None or user is None or not user.is_active or not user.can("data.write"):
        raise JobError("forbidden", Msg("jobs.no_permission_for", action=action))
    try:
        membership = get_membership(db, user, ctx.project_id)
    except AppError:
        raise JobError("forbidden", Msg("jobs.not_member")) from None
    if membership.role != "owner":
        raise JobError("forbidden", Msg("jobs.owner_only_for", action=action))
    return run


def _recheck(ctx: JobContext, params: DumpApplyParams) -> tuple[DumpPreviewParams, dict[str, Any]]:
    """Vuelve a comprobar en el worker permiso, rol owner, vista previa y destino (pudieron cambiar al encolar)."""
    with new_session() as db:
        run = _check_writer(db, ctx, Msg("jobs.action.dump"))
        preview_run = db.get(Run, params.preview_run)
        if preview_run is None or preview_run.project_id != ctx.project_id:
            raise JobError("invalid_params", Msg("jobs.preview_gone"))
        try:
            preview = load_preview(db, preview_run, ctx.settings)
        except AppError:
            raise JobError("invalid_params", Msg("jobs.preview_unavailable")) from None
        preview_params = DumpPreviewParams.model_validate(preview_run.params)
        changed = connections_changed(db, run.project, preview_run.params, preview)
        if changed:
            raise JobError("preview_changed", changed)
        link = get_project_connection(db, run.project, preview_params.target_connection)
        if link.connection.read_only:
            raise JobError("forbidden", Msg("jobs.target_read_only"))
        if link.connection.db_type != preview["target_engine"]:
            raise JobError("invalid_params", Msg("jobs.target_engine_changed", engine=preview["target_engine"]))
        return preview_params, preview


def run_apply(ctx: JobContext) -> None:
    params = DumpApplyParams.model_validate(ctx.params)
    ctx.progress("preparing", "Comprobando permiso, vista previa y destino")
    preview_params, preview = _recheck(ctx, params)
    if ctx.cancel_requested():  # pedida mientras se comprobaba: aún no se ha tocado el destino
        raise JobError("cancelled", Msg("jobs.cancelled_before_write"))
    source, target = _endpoints(ctx, preview_params)
    verb = "Vaciando y cargando" if preview_params.truncate_target else "Cargando"
    ctx.progress("running", f"{verb} {len(preview['tables'])} tablas en «{preview_params.target_connection}»")
    # Cancelar para entre lotes (util_bbdd 4.4.0, G1): la tabla en curso se deshace y las constraints se reactivan.
    progress = DumpProgress(lambda message, pct: ctx.progress("running", message, pct), ctx.cancel_requested)
    # Destino junto al diario de constraints (G31): si el proceso muere, ``dump_restore`` sabe a qué conexión volver.
    target_link = {"alias": preview_params.target_connection, "connection_id": preview["target_connection_id"]}
    _write(ctx.run_dir / DUMP_TARGET_PATH, target_link)
    try:
        result = run_dump(
            source,
            target,
            options=_options(preview_params),
            expected_structure=preview["structure_hash"],
            outputs_dir=ctx.run_dir / "outputs",
            work_dir=ctx.run_dir / "work",
            progress=progress,
        )
    except PreviewChangedError:
        raise JobError("preview_changed", Msg("jobs.dump.structure_changed")) from None
    except Exception as exc:  # frontera de util_bbdd
        ctx.logger.error("Volcado fallido", extra={"exc_type": type(exc).__name__})
        raise _job_error(exc) from None
    _write(ctx.run_dir / RESULT_PATH, result)
    # Diario pendiente: alguna constraint no se reactivó (también al cancelar); se restauran desde el resultado.
    pending = (ctx.run_dir / DUMP_JOURNAL_PATH).is_file()
    if result.get("cancelled"):
        loaded, total = len(result["completed_tables"]), sum(1 for t in preview["tables"] if t["target_table"])
        ctx.logger.info("Volcado cancelado", extra={"completed": loaded, "tables": total, "pending": pending})
        key = "jobs.dump.cancelled_pending" if pending else "jobs.dump.cancelled"
        raise JobError("cancelled", Msg(key, loaded=loaded, total=total))
    failed = [t["table"] for t in result["tables"] if t["status"] == "error"]
    broken = [f"{c['table']}.{c['constraint']}" for c in result["constraints"] if c["status"] == "failed"]
    loaded = sum(max(t["target_rows_after"] - t["target_rows_before"], 0) for t in result["tables"])
    ctx.logger.info(
        "Volcado", extra={"failed": failed, "constraints_failed": broken, "rows": loaded, "pending": pending}
    )
    if failed or broken or pending:
        parts: list[Msg] = []
        if failed:
            parts.append(Msg("jobs.dump.failed_tables", tables=", ".join(failed)))
        if broken:
            parts.append(Msg("jobs.dump.broken_constraints", constraints=", ".join(broken)))
        if pending:
            parts.append(Msg("jobs.dump.pending_constraints"))
        raise JobError("dump_partial", Msg("jobs.dump.partial", details=msg_list(parts)))
    rejected = sum(t["rows_rejected"] for t in result["tables"])
    extra = f", {rejected} filas apartadas en rechazos.csv" if rejected else ""
    ctx.progress("reporting", f"{len(result['tables'])} tablas volcadas{extra}", 100)


def run_restore(ctx: JobContext) -> None:
    """Reactiva las constraints de un volcado interrumpido desde su diario (G31); mismos controles que el volcado."""
    params = DumpRestoreParams.model_validate(ctx.params)
    ctx.progress("preparing", "Comprobando permiso, volcado y destino")
    with new_session() as db:
        run = _check_writer(db, ctx, Msg("jobs.action.restore"))
        try:
            link, journal = restore_target(db, run.project, db.get(Run, params.dump_run), ctx.settings)
        except AppError as exc:
            raise JobError("invalid_params", exc.detail or exc.title) from None
        alias = link.alias
        if params.confirm != alias:
            raise JobError("invalid_params", Msg("jobs.dump.confirm_mismatch"))
    db_type, conn_params = ctx.connection_params(alias)
    ctx.progress("running", f"Reactivando las constraints de «{alias}»")
    try:
        result = restore_constraints(Endpoint(db_type, conn_params, None), journal)
    except ValueError:
        raise JobError("invalid_params", Msg("jobs.dump.journal_invalid")) from None
    except Exception as exc:  # frontera de util_bbdd
        ctx.logger.error("Restauración de constraints fallida", extra={"exc_type": type(exc).__name__})
        raise _job_error(exc) from None
    _write(ctx.run_dir / RESTORE_PATH, result)
    failed = [f"{c['table']}.{c['constraint']}" for c in result["constraints"] if c["status"] == "failed"]
    ctx.logger.info("Constraints restauradas", extra={"failed": failed, "pending": result["pending"]})
    if result["pending"]:
        if failed:
            raise JobError("restore_partial", Msg("jobs.dump.restore_partial_list", constraints=", ".join(failed)))
        raise JobError("restore_partial", Msg("jobs.dump.restore_partial"))
    ctx.progress("reporting", f"{len(result['constraints'])} constraints reactivadas en «{alias}»", 100)
