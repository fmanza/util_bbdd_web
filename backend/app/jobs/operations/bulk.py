"""``bulk_preview`` y ``bulk_apply``: carga bulk desde fichero con util_bbdd como ejecuciones (Fase 9, ADR-010)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from app.core.errors import AppError
from app.db.models import Run, User
from app.db.session import new_session
from app.domain.projects.service import get_membership, get_project_connection
from app.domain.runs.bulks import PREVIEW_PATH, RESULT_PATH, load_preview, project_upload, target_changed
from app.domain.runs.operations import BulkApplyParams, BulkPreviewParams
from app.domain.uploads.errors import UploadContentError
from app.domain.uploads.files import ReadOptions, read_frame
from app.domain.uploads.service import upload_file
from app.integrations.util_bbdd.bulk import (
    BulkOptions,
    MatchesChangedError,
    StructureChangedError,
    Target,
    build_bulk_preview,
    run_bulk,
)
from app.integrations.util_bbdd.compare import SchemaNotFoundError
from app.integrations.util_bbdd.isolated import classify
from app.integrations.util_bbdd.progress import RunProgress
from app.jobs.context import JobContext, JobError
from app.jobs.operations.documentation import _MESSAGES


def _options(params: BulkPreviewParams, *, require_atomic: bool = False) -> BulkOptions:
    return BulkOptions(
        table=params.table,
        operation=params.operation,
        mapping=dict(params.mapping),
        on_error=params.on_error,
        max_rejects=params.max_rejects,
        parallel=params.parallel,
        chunk_size=params.chunk_size,
        require_atomic=require_atomic,
        override_identity=params.override_identity,
        sync_pk_sequences=params.sync_pk_sequences,
        exclude_autoincrement_pk=params.exclude_autoincrement_pk,
    )


def _job_error(exc: Exception) -> JobError:
    if isinstance(exc, JobError):
        return exc
    if isinstance(exc, UploadContentError):
        return JobError("invalid_file", str(exc.detail or exc))
    if isinstance(exc, LookupError | SchemaNotFoundError):
        return JobError("invalid_params", str(exc))
    code = classify(exc)
    return JobError(code, _MESSAGES.get(code, f"util_bbdd falló ({type(exc).__name__})."))


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def _source(ctx: JobContext, params: BulkPreviewParams) -> tuple[Path, str, dict[str, Any]]:
    """Fichero de la carga (ruta, tipo) y datos que fija la vista previa: id de la conexión y huella del fichero."""
    with new_session() as db:
        run = db.get(Run, ctx.run_id)
        if run is None:
            raise JobError("invalid_params", "La ejecución ya no existe.")
        upload = project_upload(db, run.project, params.upload)
        if upload is None:
            raise JobError("invalid_params", "El fichero ya no existe en el proyecto.")
        try:
            link = get_project_connection(db, run.project, params.target_connection)
        except AppError:
            raise JobError("invalid_params", "El proyecto ya no tiene la conexión destino.") from None
        fixed = {
            "target_connection_id": link.connection_id,
            "upload_sha256": upload.sha256,
            "upload_filename": upload.filename,
        }
        return upload_file(upload, ctx.settings), upload.kind, fixed


def _frame(ctx: JobContext, params: BulkPreviewParams, path: Path, kind: str) -> Any:
    options = ReadOptions(sheet=params.sheet, delimiter=params.delimiter, encoding=params.encoding)
    return read_frame(path, kind, options, max_rows=ctx.settings.bulk_max_rows)  # type: ignore[arg-type]


def run_preview(ctx: JobContext) -> None:
    params = BulkPreviewParams.model_validate(ctx.params)
    ctx.progress("preparing", "Leyendo el fichero")
    path, kind, fixed = _source(ctx, params)
    db_type, conn_params = ctx.connection_params(params.target_connection)
    ctx.progress("running", f"Validando contra «{params.table}» y generando el SQL")
    try:
        frame = _frame(ctx, params, path, kind)
        preview = build_bulk_preview(
            Target(db_type, conn_params, params.target_schema), frame, _options(params),
            outputs_dir=ctx.run_dir / "outputs", work_dir=ctx.run_dir / "work",
        )  # fmt: skip
    except Exception as exc:  # frontera de util_bbdd/pandas: el log solo lleva el tipo
        ctx.logger.error("Vista previa de carga fallida", extra={"exc_type": type(exc).__name__})
        raise _job_error(exc) from None
    preview.update(fixed, target_engine=db_type)
    _write(ctx.run_dir / PREVIEW_PATH, preview)
    problems = f", {len(preview['errors'])} errores de validación" if preview["errors"] else ""
    ctx.progress("reporting", f"{preview['rows']} filas en el fichero{problems}", 100)


def _recheck(ctx: JobContext, params: BulkApplyParams) -> tuple[BulkPreviewParams, dict[str, Any]]:
    """Vuelve a comprobar en el worker permiso, rol owner, vista previa, fichero y destino."""
    with new_session() as db:
        run = db.get(Run, ctx.run_id)
        user = db.get(User, run.user_id) if run and run.user_id else None
        if run is None or user is None or not user.is_active or not user.can_write_data:
            raise JobError("forbidden", "El usuario ya no tiene permiso para escribir datos.")
        try:
            membership = get_membership(db, user, ctx.project_id)
        except AppError:
            raise JobError("forbidden", "El usuario ya no es miembro del proyecto.") from None
        if membership.role != "owner":
            raise JobError("forbidden", "Solo el propietario del proyecto puede cargar datos.")
        preview_run = db.get(Run, params.preview_run)
        if preview_run is None or preview_run.project_id != ctx.project_id:
            raise JobError("invalid_params", "La vista previa ya no existe.")
        try:
            preview = load_preview(db, preview_run, ctx.settings)
        except AppError:
            raise JobError("invalid_params", "La vista previa ya no está disponible (¿purgada?).") from None
        changed = target_changed(db, run.project, preview_run.params, preview)
        if changed:
            raise JobError("preview_changed", changed)
        preview_params = BulkPreviewParams.model_validate(preview_run.params)
        link = get_project_connection(db, run.project, preview_params.target_connection)
        if link.connection.read_only:
            raise JobError("forbidden", "La conexión destino es de solo lectura.")
        if link.connection.db_type != preview["target_engine"]:
            raise JobError("invalid_params", f"La conexión destino ya no es {preview['target_engine']}.")
        return preview_params, preview


def run_apply(ctx: JobContext) -> None:
    params = BulkApplyParams.model_validate(ctx.params)
    ctx.progress("preparing", "Comprobando permiso, vista previa, fichero y destino")
    preview_params, preview = _recheck(ctx, params)
    if ctx.cancel_requested():  # pedida mientras se comprobaba: aún no se ha tocado el destino
        raise JobError("cancelled", "Cancelada por un usuario antes de escribir en el destino.")
    path, kind, _ = _source(ctx, preview_params)
    db_type, conn_params = ctx.connection_params(preview_params.target_connection)
    ctx.progress("running", f"{preview['operation'].upper()} de {preview['rows']} filas en «{preview['table']}»")
    # Cancelar para entre lotes (util_bbdd 4.5.0, G1): en una sola transacción se deshace la carga entera.
    progress = RunProgress(
        lambda message, pct: ctx.progress("running", message, pct), ctx.cancel_requested, ["rows"], {"rows": "Filas"}
    )
    try:
        frame = _frame(ctx, preview_params, path, kind)
        result = run_bulk(
            Target(db_type, conn_params, preview_params.target_schema), frame,
            # Sin aceptar que no sea atómica, util_bbdd lo garantiza aunque su plan haya cambiado (G36).
            _options(preview_params, require_atomic=not params.accept_non_atomic),
            expected_structure=preview["structure_hash"], outputs_dir=ctx.run_dir / "outputs",
            expected_matches=params.confirm_rows, progress=progress,
        )  # fmt: skip
    except StructureChangedError:
        raise JobError("preview_changed", "La tabla o el mapeo cambiaron desde la vista previa: repítela.") from None
    except MatchesChangedError as exc:
        raise JobError(
            "preview_changed",
            f"Ahora coinciden {exc} filas, no las {params.confirm_rows} confirmadas: repite la vista previa.",
        ) from None
    except Exception as exc:  # frontera de util_bbdd
        ctx.logger.error("Carga fallida", extra={"exc_type": type(exc).__name__})
        raise _job_error(exc) from None
    _write(ctx.run_dir / RESULT_PATH, result)
    changed = abs(result["target_rows_after"] - result["target_rows_before"])
    ctx.logger.info(
        "Carga",
        extra={
            "operation": result["operation"], "rows": result["rows"], "committed": result["committed"],
            "changed": changed, "applied": applied_rows(result), "verified": result["verified"],
        },
    )  # fmt: skip
    failed = [p["index"] for p in result["partitions"] if p["error"]]
    if result["cancelled"]:
        kept = (
            f"quedan confirmadas {result['committed']} filas de las particiones terminadas"
            if result["committed"]
            else "la carga se deshizo entera; no se escribió nada"
        )
        raise JobError("cancelled", f"Cancelada por un usuario: {kept}.")
    if result["error"]:
        raise JobError("bulk_failed", f"La carga falló: {result['error']}")
    if failed:
        raise JobError("bulk_partial", f"Fallaron {len(failed)} particiones; las demás quedaron confirmadas.")
    ctx.progress("reporting", result_message(result), 100)


#: Participio de cada operación para el mensaje final.
_DONE: Final[dict[str, str]] = {
    "insert": "insertadas", "update": "actualizadas (enviadas sin rechazo)", "delete": "borradas",
}  # fmt: skip


def applied_rows(result: dict[str, Any]) -> int:
    """Filas que la carga cambió en el destino.

    ``committed`` de util_bbdd cuenta las filas enviadas, también las apartadas (G37): en un insert o un borrado manda
    el recuento de la tabla; en una actualización, que no cambia el recuento, las enviadas menos las apartadas
    (incluye las claves que no existían).
    """
    if result["operation"] == "insert":
        return int(result["target_rows_after"]) - int(result["target_rows_before"])
    if result["operation"] == "delete":
        return int(result["target_rows_before"]) - int(result["target_rows_after"])
    return int(result["committed"] or 0) - int(result["rejected"] or 0)


def result_message(result: dict[str, Any]) -> str:
    """Mensaje final de una carga terminada: filas aplicadas, apartadas y aviso si todas se apartaron."""
    operation = result["operation"].upper()
    rejected = int(result["rejected"] or 0)
    if result["rows"] and rejected == result["rows"]:
        return f"{operation} terminado sin cargar ninguna fila: las {rejected} se apartaron en rechazos.csv"
    extra = f", {rejected} filas apartadas en rechazos.csv" if rejected else ""
    # G37: el recuento del destino se mantiene como verificación de lo que util_bbdd dice haber confirmado.
    check = "; el recuento del destino no cuadra: revisa el resultado" if result["verified"] is False else ""
    sync_errors = [s["error"] or s["status"] for s in result.get("pk_sync", []) if s["status"] == "error"]
    sync = f"; no se pudo ajustar el contador de la PK: {sync_errors[0]}" if sync_errors else ""
    return f"{operation} terminado: {applied_rows(result)} filas {_DONE[result['operation']]}{extra}{check}{sync}"
