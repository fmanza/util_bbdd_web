"""``noop``: valida el motor de ejecuciones (progreso, cancelación, fallos, artefactos y conexiones del proyecto)."""

from __future__ import annotations

import html
import time

from app.domain.runs.operations import NoopParams
from app.jobs.context import JobContext, JobError


def run(ctx: JobContext) -> None:
    params = NoopParams.model_validate(ctx.params)
    ctx.progress("preparing", "Preparando", 0)
    version: str | None = None
    db_type: str | None = None
    if params.connection:
        ctx.progress("connecting", f"Probando la conexión «{params.connection}»")
        db_type, version = ctx.test_connection(params.connection)
    for step in range(1, params.steps + 1):
        time.sleep(params.step_seconds)
        ctx.progress("running", f"Paso {step} de {params.steps}", int(step * 100 / params.steps))
    if params.fail:
        raise JobError("noop_failed", "Fallo simulado (fail = true).")

    ctx.progress("reporting", "Generando artefactos de ejemplo", 100)
    connection_line = (
        f"Conexión «{params.connection}» ({db_type}): servidor {version or 'versión desconocida'}."
        if params.connection
        else "Sin conexión."
    )
    (ctx.outputs("markdown") / "resumen.md").write_text(
        f"# Ejecución {ctx.run_id}\n\n- Operación: `noop`\n- Pasos: {params.steps}\n- {connection_line}\n",
        encoding="utf-8",
    )
    (ctx.outputs("html") / "resumen.html").write_text(
        '<!doctype html><html lang="es"><meta charset="utf-8"><title>noop</title>'
        f"<h1>Ejecución {html.escape(ctx.run_id)}</h1><p>{html.escape(connection_line)}</p>"
        "<script>document.body.innerHTML = 'scripts no permitidos';</script></html>",
        encoding="utf-8",
    )
    (ctx.outputs("sql") / "ejemplo.sql").write_text(
        f"-- Script de ejemplo generado por noop ({ctx.run_id})\nSELECT 1 AS ok;\n", encoding="utf-8"
    )
    (ctx.outputs("graphs") / "pasos.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="40">'
        + "".join(f'<rect x="{i * 22}" y="8" width="18" height="24" fill="#228be6"/>' for i in range(params.steps))
        + "</svg>",
        encoding="utf-8",
    )
