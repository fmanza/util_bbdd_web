"""``documentation`` y ``relationship_graph``: documentación y grafos de util_bbdd como ejecuciones (Fase 5).

Plantillas (ADR-011): se copian a ``inputs/`` tras comprobar su SHA-256 (la ejecución no depende de que sigan
existiendo); si no están o no se pueden aplicar, la documentación sale con el formato por defecto y un aviso.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.db.models import Project
from app.db.session import new_session
from app.domain.runs.operations import DocumentationParams, RelationshipGraphParams
from app.domain.templates.errors import TemplateNotFoundError
from app.domain.templates.files import STORED_SUFFIX, Kind
from app.domain.templates.service import resolve_for_run, template_file
from app.integrations.util_bbdd.documentation import (
    DocumentationOptions,
    DocumentTemplates,
    GraphOptions,
    GraphvizMissingError,
    generate_documentation,
    generate_graphs,
    graphviz_failed,
)
from app.integrations.util_bbdd.isolated import classify
from app.integrations.util_bbdd.progress import RunProgress, is_cancellation
from app.jobs.context import JobContext, JobError
from app.workspace.layout import TEMPLATES_INPUT, write_json_atomic

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
    if is_cancellation(exc):
        return JobError("cancelled", "Cancelada por un usuario.")
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


_LABELS = {"word": ("Word", "el documento Word"), "excel": ("Excel", "el libro Excel")}
#: Fases de util_bbdd en el mensaje de progreso del run.
_PHASES = {"metadata": "Leyendo el catálogo", "word": "Word", "excel": "Excel", "html": "HTML"}


def _copy_template(ctx: JobContext, project: Project | None, template_id: str, kind: Kind) -> tuple[Any, Path] | None:
    """Plantilla del proyecto o global copiada en ``inputs/`` (``None`` si ya no está o su contenido cambió)."""
    with new_session() as db:
        template = resolve_for_run(db, project, template_id, kind) if project is not None else None
        if template is None:
            return None
        db.expunge(template)
    try:
        data = template_file(template, ctx.settings).read_bytes()
    except (TemplateNotFoundError, OSError, ValueError):
        return None
    if hashlib.sha256(data).hexdigest() != template.sha256:
        return None
    target = ctx.run_dir / "inputs" / f"plantilla_{kind}.{STORED_SUFFIX[kind]}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return template, target


def _templates(
    ctx: JobContext, params: DocumentationParams
) -> tuple[DocumentTemplates, list[dict[str, Any]], list[str]]:
    """Plantillas elegidas (copias en ``inputs/``), su registro para ``run.json`` y los avisos de las que faltan."""
    chosen: dict[Kind, str | None] = {"word": params.word_template, "excel": params.excel_template}
    paths: dict[str, Any] = {}
    entries: list[dict[str, Any]] = []
    warnings: list[str] = []
    if not any(chosen.values()):
        return DocumentTemplates(), entries, warnings
    with new_session() as db:
        project = db.get(Project, ctx.project_id)
        if project is not None:
            db.expunge(project)
    for kind, template_id in chosen.items():
        if not template_id:
            continue
        found = _copy_template(ctx, project, template_id, kind)
        if found is None:
            label, output = _LABELS[kind]
            warnings.append(f"La plantilla {label} ya no está disponible: {output} usa el formato por defecto.")
            entries.append({"kind": kind, "id": template_id, "applied": False})
            continue
        template, path = found
        paths[kind], paths[f"{kind}_table_style"] = path, template.table_style
        entries.append({
            "kind": kind, "id": template.id, "scope": "global" if template.project_id is None else "project",
            "name": template.name, "sha256": template.sha256,
        })  # fmt: skip
    return DocumentTemplates(**paths), entries, warnings


def _record(ctx: JobContext, entries: list[dict[str, Any]], warnings: list[str]) -> None:
    """``inputs/templates.json``: lo recoge ``run.json`` al cerrar el run."""
    if entries or warnings:
        write_json_atomic(ctx.run_dir / TEMPLATES_INPUT, {"templates": entries, "warnings": warnings})


def run_documentation(ctx: JobContext) -> None:
    params = DocumentationParams.model_validate(ctx.params)
    ctx.progress("connecting", f"Preparando la conexión «{params.connection}»")
    db_type, conn_params = ctx.connection_params(params.connection)
    formats = tuple(f for f in ("word", "excel", "html") if getattr(params, f))
    options = DocumentationOptions(
        formats=formats,
        **params.model_dump(include=set(DocumentationOptions.__dataclass_fields__) - {"formats"}),
    )
    templates, entries, warnings = _templates(ctx, params)
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
            templates=templates,
            progress=RunProgress(
                lambda message, pct: ctx.progress("running", message, pct),
                ctx.cancel_requested,
                ("metadata", *formats),
                _PHASES,
            ),
        )
    except Exception as exc:  # frontera de util_bbdd: el log solo lleva el tipo
        _record(ctx, entries, warnings)
        if is_cancellation(exc):
            ctx.logger.info("Documentación cancelada entre tablas")
            raise _job_error(exc) from None
        ctx.logger.error("Documentación fallida", extra={"exc_type": type(exc).__name__})
        raise _job_error(exc) from None
    applied: dict[str, bool] = summary.pop("templates_applied")
    for entry in entries:
        entry.setdefault("applied", applied.get(entry["kind"], False))
    warnings += summary.pop("warnings")
    _record(ctx, entries, warnings)
    ctx.logger.info("Documentación generada", extra={**summary, "warnings": len(warnings)})
    notice = " (con avisos)" if warnings else ""
    ctx.progress(
        "reporting",
        f"{summary['tables']} tablas, {summary['views']} vistas y {summary['routines']} rutinas documentadas{notice}",
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
