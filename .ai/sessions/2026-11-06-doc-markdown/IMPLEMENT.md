# IMPLEMENT — Documentación Markdown (util_bbdd 5.3.0)

Aprobado por el usuario el 2026-11-06 («El wheel ya está. IMPLEMENT»). Las dos decisiones abiertas del AUDIT_PLAN
no se respondieron; se aplicó la propuesta: **mapa inválido = la ejecución falla** (`invalid_trace_map`) y **una sola
entrega** (sin subir la versión: eso es VERSION).

## Condiciones del AUDIT_PLAN

| Condición | Resultado |
|---|---|
| T1 wheel 5.3.0 | Publicado; el hash de `uv.lock` coincide con `util_bbdd-5.3.0-py3-none-any.whl.sha256` |
| T6 listado por operación | `GET /projects/{id}/runs` ya filtra por `status` y `operation` (`useSucceededRuns`) |
| S1 rutas en mensajes | `public_message` + test API (ni `workspace_dir` ni `inputs/` en el error ni en `run.log`) |
| S2 IDOR de la anterior | `documentations.previous_catalog` (mismo proyecto, «no existe en el proyecto» sin revelar) + test |
| T2 volumen | 500 tablas solo Markdown (SQLite): 3,0 s, 511 artefactos, registro 2,9 s, 2,8 MB (sin `mermaid.min.js`) |

## Bloques

- **A** `pyproject.toml`/`uv.lock` → 5.3.0 (solo cambia util_bbdd).
- **B** `integrations/util_bbdd/documentation.py`: `MARKDOWN`, carpeta entera, bloque `imprimir["markdown"]`,
  `MarkdownInputs`, `MarkdownInputError`/`markdown_input_error`/`public_message`, Graphviz solo para Word/HTML.
  `jobs/operations/documentation.py`: formato, fase, Mermaid local con aviso, mapa y `catalog.json` anterior copiados
  a `inputs/`, mapa en `run.json`.
- **C** `DocumentationParams` (+5 campos, `requires`), `OperationParam(Out)` con tipo `run`, `run_operation` y
  `requires`; formulario genérico con `requires` y selector de ejecución anterior.
- **D** Tipo `trace` en plantillas (sin migración), ejemplo base, descarga con la extensión guardada; panel.
- **E** `domain/runs/documentations.py` (al encolar y en el worker), `load_diff` para documentación,
  `RunDetailOut.has_diff`, visor sin evolución.
- **F** Vista previa sin front matter (`markdown.ts`), tarjeta «Documentación Markdown».
- **G** OpenAPI + `gen:api`, guía `documentacion.md`, ADR-011 (enmienda), GAPS G49, ROADMAP, CHANGELOG.

## Validación

- Backend: ruff format/check, mypy, `export_openapi.py --check` OK. `pytest -m "not integration"`: 769 passed,
  2 skipped. Suite completa: los únicos fallos son de integración contra SQL Server (`Unable to connect … 127.0.0.1`,
  también en tests no tocados como `test_bench_engines::test_bench_connection`): entorno.
- Frontend: format:check, lint, typecheck, `npm test` (22 ficheros, 159 tests) y build OK.
- Docs: `zensical build --strict` OK.
