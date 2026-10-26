"""``compare``: comparación de esquemas de util_bbdd como ejecución (Fase 6)."""

from __future__ import annotations

from app.domain.runs.operations import CompareParams
from app.integrations.util_bbdd.compare import (
    REPORT_FORMATS,
    CompareOptions,
    SchemaNotFoundError,
    Side,
    SideError,
    compare_schemas,
    progress_phases,
)
from app.integrations.util_bbdd.isolated import classify
from app.integrations.util_bbdd.progress import RunProgress, is_cancellation
from app.jobs.context import JobContext, JobError
from app.jobs.operations.documentation import _MESSAGES

_SIDES = {"source": "origen", "target": "destino"}
#: Fases de util_bbdd en el mensaje de progreso del run.
_PHASES = {"metadata": "Leyendo el catálogo", "tables": "Tablas", "views": "Vistas", "routines": "Rutinas"}


def _job_error(exc: Exception) -> JobError:
    """Error saneado: código estable, lado afectado y mensaje propio (nunca el texto del driver)."""
    if isinstance(exc, JobError):
        return exc
    if is_cancellation(exc):
        return JobError("cancelled", "Cancelada por un usuario.")
    if isinstance(exc, SchemaNotFoundError):
        return JobError("invalid_params", str(exc))
    if isinstance(exc, SideError):
        code = classify(exc.cause)
        base = _MESSAGES.get(code, f"util_bbdd falló ({type(exc.cause).__name__}).")
        return JobError(code, f"{_SIDES[exc.side].capitalize()}: {base}")
    code = classify(exc)
    return JobError(code, _MESSAGES.get(code, f"util_bbdd falló ({type(exc).__name__})."))


def _side(ctx: JobContext, alias: str, schema: str | None, side: str) -> Side:
    try:
        db_type, conn_params = ctx.connection_params(alias)
    except JobError as exc:
        raise JobError(exc.code, f"{_SIDES[side].capitalize()}: {exc.message}") from None
    return Side(db_type=db_type, conn_params=conn_params, schema=schema, alias=alias)


def run(ctx: JobContext) -> None:
    params = CompareParams.model_validate(ctx.params)
    ctx.progress("connecting", "Preparando las conexiones")
    source = _side(ctx, params.source_connection, params.source_schema, "source")
    target = _side(ctx, params.target_connection, params.target_schema, "target")
    options = CompareOptions(
        tables=params.tables,
        views=params.views,
        indexes=params.indexes,
        foreign_keys=params.foreign_keys,
        comments=params.comments,
        routines=params.routines,
        formats=tuple(f for f in REPORT_FORMATS if getattr(params, f)),
        sql_dialect=params.sql_dialect,
    )
    try:
        summary = compare_schemas(
            source,
            target,
            options=options,
            outputs_dir=ctx.run_dir / "outputs",
            on_phase=lambda phase, message: ctx.progress(phase, message),
            progress=RunProgress(
                lambda message, pct: ctx.progress("running", message, pct),
                ctx.cancel_requested,
                progress_phases(options),
                _PHASES,
            ),
        )
    except Exception as exc:  # frontera de util_bbdd: el log solo lleva el tipo
        if is_cancellation(exc):
            ctx.logger.info("Comparación cancelada entre tablas")
            raise _job_error(exc) from None
        cause = exc.cause if isinstance(exc, SideError) else exc
        ctx.logger.error("Comparación fallida", extra={"exc_type": type(cause).__name__})
        raise _job_error(exc) from None
    ctx.logger.info("Comparación terminada", extra=summary)
    ctx.progress("reporting", str(summary["summary"]), 100)
