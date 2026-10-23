"""``dump_preview`` y ``dump_apply``: volcado de datos de util_bbdd como ejecuciones (Fase 8, ADR-009)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.errors import AppError
from app.db.models import Run, User
from app.db.session import new_session
from app.domain.projects.service import get_membership, get_project_connection
from app.domain.runs.dumps import PREVIEW_PATH, RESULT_PATH, connections_changed, load_preview
from app.domain.runs.operations import DumpApplyParams, DumpPreviewParams
from app.integrations.util_bbdd.compare import SchemaNotFoundError
from app.integrations.util_bbdd.dump import (
    DumpOptions,
    Endpoint,
    PreviewChangedError,
    UnknownTablesError,
    build_preview,
    parse_tables,
    run_dump,
)
from app.integrations.util_bbdd.isolated import classify
from app.jobs.context import JobContext, JobError
from app.jobs.operations.documentation import _MESSAGES


def _options(params: DumpPreviewParams) -> DumpOptions:
    return DumpOptions(
        tables=parse_tables(params.tables),
        truncate_target=params.truncate_target,
        on_error=params.on_error,
        max_rejects=params.max_rejects,
        chunk_size=params.chunk_size,
        max_parallel_tables=params.max_parallel_tables,
        manage_indexes=params.manage_indexes,
        sync_pk_sequences=params.sync_pk_sequences,
    )


def _endpoints(ctx: JobContext, params: DumpPreviewParams) -> tuple[Endpoint, Endpoint]:
    source = ctx.connection_params(params.source_connection)
    target = ctx.connection_params(params.target_connection)
    return Endpoint(*source, params.source_schema), Endpoint(*target, params.target_schema)


def _job_error(exc: Exception) -> JobError:
    if isinstance(exc, JobError):
        return exc
    if isinstance(exc, SchemaNotFoundError | UnknownTablesError):
        prefix = "Tablas que no existen en el origen: " if isinstance(exc, UnknownTablesError) else ""
        return JobError("invalid_params", f"{prefix}{exc}")
    code = classify(exc)
    return JobError(code, _MESSAGES.get(code, f"util_bbdd falló ({type(exc).__name__})."))


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
            raise JobError("invalid_params", "La ejecución ya no existe.")
        return {
            f"{side}_connection_id": get_project_connection(db, run.project, alias).connection_id
            for side, alias in (("source", params.source_connection), ("target", params.target_connection))
        }


def _recheck(ctx: JobContext, params: DumpApplyParams) -> tuple[DumpPreviewParams, dict[str, Any]]:
    """Vuelve a comprobar en el worker permiso, rol owner, vista previa y destino (pudieron cambiar al encolar)."""
    with new_session() as db:
        run = db.get(Run, ctx.run_id)
        user = db.get(User, run.user_id) if run and run.user_id else None
        if run is None or user is None or not user.is_active or not user.can_write_data:
            raise JobError("forbidden", "El usuario ya no tiene permiso para volcar datos.")
        try:
            membership = get_membership(db, user, ctx.project_id)
        except AppError:
            raise JobError("forbidden", "El usuario ya no es miembro del proyecto.") from None
        if membership.role != "owner":
            raise JobError("forbidden", "Solo el propietario del proyecto puede volcar datos.")
        preview_run = db.get(Run, params.preview_run)
        if preview_run is None or preview_run.project_id != ctx.project_id:
            raise JobError("invalid_params", "La vista previa ya no existe.")
        try:
            preview = load_preview(db, preview_run, ctx.settings)
        except AppError:
            raise JobError("invalid_params", "La vista previa ya no está disponible (¿purgada?).") from None
        preview_params = DumpPreviewParams.model_validate(preview_run.params)
        changed = connections_changed(db, run.project, preview_run.params, preview)
        if changed:
            raise JobError("preview_changed", changed)
        link = get_project_connection(db, run.project, preview_params.target_connection)
        if link.connection.read_only:
            raise JobError("forbidden", "La conexión destino es de solo lectura.")
        if link.connection.db_type != preview["target_engine"]:
            raise JobError("invalid_params", f"La conexión destino ya no es {preview['target_engine']}.")
        return preview_params, preview


def run_apply(ctx: JobContext) -> None:
    params = DumpApplyParams.model_validate(ctx.params)
    ctx.progress("preparing", "Comprobando permiso, vista previa y destino")
    preview_params, preview = _recheck(ctx, params)
    source, target = _endpoints(ctx, preview_params)
    verb = "Vaciando y cargando" if preview_params.truncate_target else "Cargando"
    ctx.progress("running", f"{verb} {len(preview['tables'])} tablas en «{preview_params.target_connection}»")
    try:
        result = run_dump(
            source,
            target,
            options=_options(preview_params),
            expected_structure=preview["structure_hash"],
            outputs_dir=ctx.run_dir / "outputs",
            work_dir=ctx.run_dir / "work",
        )
    except PreviewChangedError:
        raise JobError("preview_changed", "Las tablas o columnas cambiaron desde la vista previa: repítela.") from None
    except Exception as exc:  # frontera de util_bbdd
        ctx.logger.error("Volcado fallido", extra={"exc_type": type(exc).__name__})
        raise _job_error(exc) from None
    _write(ctx.run_dir / RESULT_PATH, result)
    failed = [t["table"] for t in result["tables"] if t["status"] == "error"]
    broken = [f"{c['table']}.{c['constraint']}" for c in result["constraints"] if c["status"] == "failed"]
    loaded = sum(max(t["target_rows_after"] - t["target_rows_before"], 0) for t in result["tables"])
    ctx.logger.info("Volcado", extra={"failed": failed, "constraints_failed": broken, "rows": loaded})
    if failed or broken:
        parts = []
        if failed:
            parts.append(f"tablas con error: {', '.join(failed)}")
        if broken:
            parts.append(f"constraints que no se pudieron reactivar: {', '.join(broken)}")
        raise JobError("dump_partial", "Volcado incompleto; " + "; ".join(parts) + ".")
    rejected = sum(t["rows_rejected"] for t in result["tables"])
    extra = f", {rejected} filas apartadas en rechazos.csv" if rejected else ""
    ctx.progress("reporting", f"{len(result['tables'])} tablas volcadas{extra}", 100)
