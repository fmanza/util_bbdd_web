"""``documentation`` y ``relationship_graph``: documentación y grafos de util_bbdd como ejecuciones (Fase 5)."""

from __future__ import annotations

from app.domain.runs.operations import DocumentationParams, RelationshipGraphParams
from app.integrations.util_bbdd.documentation import (
    DocumentationOptions,
    GraphOptions,
    GraphvizMissingError,
    SchemaNotSupportedError,
    generate_documentation,
    generate_graphs,
    graphviz_failed,
)
from app.integrations.util_bbdd.isolated import classify
from app.jobs.context import JobContext, JobError

_MESSAGES = {
    "connection_failed": "No se pudo conectar con la base de datos.",
    "driver_missing": "El driver del motor no está instalado en el servidor.",
    "timeout": "La base de datos no respondió a tiempo.",
    "invalid_config": "Parámetros no válidos para util_bbdd.",
}


def _job_error(exc: Exception) -> JobError:
    """Error saneado: código estable y mensaje propio (nunca el texto del driver)."""
    if isinstance(exc, JobError):
        return exc
    if isinstance(exc, SchemaNotSupportedError):
        return JobError("invalid_params", str(exc))
    if isinstance(exc, GraphvizMissingError):
        return JobError("graphviz_missing", str(exc))
    if isinstance(exc, LookupError):
        return JobError("invalid_params", str(exc))
    if graphviz_failed(exc):
        return JobError(
            "graphviz_failed",
            "Graphviz no pudo dibujar un diagrama de relaciones. Reduce la profundidad o desactiva los diagramas.",
        )
    code = classify(exc)
    return JobError(code, _MESSAGES.get(code, f"util_bbdd falló ({type(exc).__name__})."))


def run_documentation(ctx: JobContext) -> None:
    params = DocumentationParams.model_validate(ctx.params)
    ctx.progress("connecting", f"Preparando la conexión «{params.connection}»")
    db_type, conn_params = ctx.connection_params(params.connection)
    formats = tuple(f for f in ("word", "excel", "html") if getattr(params, f))
    options = DocumentationOptions(
        formats=formats,
        **params.model_dump(include=set(DocumentationOptions.__dataclass_fields__) - {"formats"}),
    )
    ctx.progress("running", f"Generando documentación ({', '.join(formats)})")
    try:
        summary = generate_documentation(
            db_type,
            conn_params,
            schema=params.schema_name,
            options=options,
            outputs_dir=ctx.run_dir / "outputs",
            work_dir=ctx.run_dir / "work",
            name="documentacion",
        )
    except Exception as exc:  # frontera de util_bbdd: el log solo lleva el tipo
        ctx.logger.error("Documentación fallida", extra={"exc_type": type(exc).__name__})
        raise _job_error(exc) from None
    ctx.logger.info("Documentación generada", extra=summary)
    ctx.progress(
        "reporting",
        f"{summary['tables']} tablas, {summary['views']} vistas y {summary['routines']} rutinas documentadas",
        100,
    )


def run_relationship_graph(ctx: JobContext) -> None:
    params = RelationshipGraphParams.model_validate(ctx.params)
    ctx.progress("connecting", f"Preparando la conexión «{params.connection}»")
    db_type, conn_params = ctx.connection_params(params.connection)
    target = params.table or "todas las tablas con relaciones"
    ctx.progress("running", f"Generando el grafo de {target}")
    try:
        summary = generate_graphs(
            db_type,
            conn_params,
            schema=params.schema_name,
            options=GraphOptions(**params.model_dump(include=set(GraphOptions.__dataclass_fields__))),
            output_dir=ctx.outputs("graphs"),
        )
    except Exception as exc:  # frontera de util_bbdd
        ctx.logger.error("Grafo fallido", extra={"exc_type": type(exc).__name__})
        raise _job_error(exc) from None
    if not summary["files"]:
        raise JobError("no_relations", "No hay relaciones que dibujar con esos parámetros.")
    ctx.logger.info("Grafo generado", extra=summary)
    ctx.progress("reporting", f"{len(summary['files'])} imágenes generadas", 100)
