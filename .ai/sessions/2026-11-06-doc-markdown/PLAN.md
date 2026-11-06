# PLAN — Documentación Markdown (util_bbdd 5.3.0)

Sesión `2026-11-06-doc-markdown` · flujo `new_feature` · web v1.10.1 → **1.11.0** · origen:
`util_bbdd/.ai/sessions/2026-11-05-doc-markdown/WEB_HANDOFF.md` (W-1…W-10).

## Objective

Añadir el formato **Markdown** a la operación `documentation`: carpeta completa con un `.md` por objeto, diagramas ER
de Mermaid (sin Graphviz), `catalog.json`, `llms*.txt` y `mkdocs.yml`; con **mapa de trazabilidad** opcional y
**cambios respecto de una documentación anterior** (`changes.json`, visible en el visor de diferencias).

## Scope and affected paths

Agrupado en bloques implementables por separado (A es requisito del resto).

### A — Dependencia (W-1)

| Ruta | Cambio |
|---|---|
| `backend/pyproject.toml` | `util_bbdd[…]==5.3.0` y URL `…/releases/download/v5.3.0/util_bbdd-5.3.0-py3-none-any.whl` (comentario ADR-006) |
| `backend/uv.lock` | `uv lock` (solo cambia util_bbdd: 5.3.0 no añade dependencias, `git diff v5.2.0 v5.3.0 -- pyproject.toml`) |

**Precondición bloqueante:** el wheel **no está publicado** en la release v5.3.0 (activos a 2026-11-06: solo
`util_bbdd-docs-5.3.0.zip[.sha256]`; la v5.2.0 sí tenía `util_bbdd-5.2.0-py3-none-any.whl[.sha256]`). Hay que
subirlo (en util_bbdd) antes de IMPLEMENT.

### B — Generación (W-2, W-3, W-4)

| Ruta | Cambio |
|---|---|
| `backend/app/integrations/util_bbdd/documentation.py` | `_FORMAT_DIRS["markdown"] = "MARKDOWN"`; en `_document`, rama `if fmt in {"html", "markdown"}` que mueve la carpeta entera a `outputs/<fmt>/documentacion` (`produced["markdown"] = "markdown/documentacion/docs/index.md"`); `DocumentationOptions` + `markdown_site_name`, `markdown_diagram_depth`, `markdown_trace_map: Path \| None`, `markdown_previous: Path \| None`, `mermaid_js: Path \| None`; `build_imprimir` añade el bloque `"markdown"` solo si se pide el formato; la comprobación de `dot` pasa a `options.graphs and {"word", "html"} & set(options.formats)` |
| `backend/app/jobs/operations/documentation.py` | `formats` incluye `"markdown"`; `_PHASES["markdown"] = "Markdown"`; `mermaid_js` de `ctx.settings.mermaid_js` si existe (mismo criterio que `_mermaid_js` de `jobs/operations/compare.py`), si no, aviso en el run; errores `DocumentationConfigError` del Markdown → `JobError` con código propio (ver D) |

### C — Parámetros y formulario (W-5)

| Ruta | Cambio |
|---|---|
| `backend/app/domain/runs/operations.py` (`DocumentationParams`) | `markdown: bool = _group("formats", False, …)` (**por defecto desactivado**: no cambia las ejecuciones actuales); grupo nuevo `markdown`: `markdown_site_name: str \| None` (≤ 100, sin caracteres de control), `markdown_diagram_depth: int = 2` (1–3), `trace_map` (`_template("trace", …)`) y `markdown_previous_run` (W-7); `_one_format` incluye Markdown y anula los campos `markdown_*` si no se pide; texto de `graphs` → «Word y HTML con Graphviz; Markdown con Mermaid» |
| `frontend/src/features/runs/LaunchRunModal.tsx` | grupo `markdown` visible solo con la casilla Markdown marcada: se generaliza la regla que ya oculta las plantillas (`template_kind` → `values[kind]`) con `ubw_requires` en `json_schema_extra` |
| `frontend/src/i18n/es/*` | textos del grupo y de los campos |

Equivalencias (sin campos nuevos): `graph_depth`, `graph_direction`, `graph_columns` (`relations_first` web =
`compact` util_bbdd) y `graph_max_columns` ya llegan por `grafo`. `graph_data_types` y `graph_orthogonal` no
aplican a Mermaid (se documenta en la ayuda).

### D — Mapa de trazabilidad (W-6)

Se reutiliza el catálogo de **plantillas** (ADR-011) con un tipo nuevo `trace` (cabe en `kind String(8)`, sin
migración: no hay `CHECK` sobre `kind`; el índice único ya incluye `kind`). Así hereda ámbito proyecto/global,
permisos, cuota por ámbito, SHA-256 y la copia a `inputs/` al lanzar.

| Ruta | Cambio |
|---|---|
| `backend/app/domain/templates/files.py` | `Kind` + `"trace"`; extensiones `.toml`/`.json`; validación propia: ≤ 1 MB (límite de util_bbdd, `_trace.MAX_BYTES`), UTF-8, sintaxis TOML/JSON (`tomllib`/`json`), objeto raíz; `table_styles=[]` |
| `backend/app/domain/templates/service.py`, `api/v1/templates.py`, `api/v1/schemas_templates.py` | aceptar `kind="trace"` (el tamaño máximo es el menor de `template_max_mb` y 1 MB) |
| `backend/app/jobs/operations/documentation.py` | `_templates` copia `inputs/trace_map.<toml\|json>` (conservando la extensión: util_bbdd decide el formato por ella) |
| `backend/app/integrations/util_bbdd/documentation.py` | `trace_map_failed(exc)` (cadena de causas, `DocumentationConfigError` con «markdown.trace_map») y `public_message(exc, inputs_dir)` que sustituye rutas del servidor por el nombre mostrado |
| Frontend `features/templates/*` | tipo «Mapa de trazabilidad» en la lista y la subida del proyecto y de Administración |

La validación **de esquema** (todos los errores) solo la hace util_bbdd al construir `DatabaseDocumentation`
(`TraceMap` es privado, `doc/infrastructure/renderers/markdown/_trace.py`): en la subida solo se valida sintaxis. Se
registra **G49** en `UTIL_BBDD_GAPS.md` (validador público del mapa) para poder validar al subir.

### E — Comparar con una ejecución anterior (W-7)

| Ruta | Cambio |
|---|---|
| `backend/app/domain/runs/operations.py` | `markdown_previous_run: str \| None` (`RUN_ID_PATTERN`, `ubw_kind="run"`, `ubw_run_operation="documentation"`) |
| `backend/app/domain/runs/service.py` | al lanzar: mismo proyecto, `operation == "documentation"`, `succeeded`, no purgada, mismo alias de conexión y mismo `schema`, con el artefacto `outputs/markdown/documentacion/docs/catalog.json` registrado → si no, 422 `invalid_params` |
| `backend/app/jobs/operations/documentation.py` | copia ese `catalog.json` a `inputs/previous/catalog.json` y lo pasa como `markdown.previous` (no depende de la carpeta del otro run ni de su retención) |
| `backend/app/domain/runs/diff.py` | `load_diff`: también `documentation` con `outputs/markdown/documentacion/docs/changes.json` (mismo `read_diff`: `changes.json` es `SchemaDiff.to_dict()`, `_changes.changes_json`); `/diff/evolution` sigue solo para `compare` |
| `backend/app/api/v1/runs.py` (detalle) | `has_diff: bool` en `RunDetailOut` para que la SPA sepa si mostrar el visor |
| `frontend/src/features/runs/LaunchRunModal.tsx` | `param.type === 'run'`: `Select` con las documentaciones terminadas del proyecto (endpoint de listado existente filtrado; **PENDIENTE DE VERIFICAR** que `GET /api/v1/runs` filtra por proyecto y operación, si no, filtro en cliente sobre la página) |
| `frontend/src/features/runs/RunDetailPage.tsx` | visor de diferencias también si `run.has_diff` |

### F — Vista previa y descarga (W-8, W-9)

- `scan_artifacts` ya recorre `outputs/**`: todos los ficheros de `outputs/markdown/documentacion/**` quedan como
  artefactos `markdown` y entran en el ZIP (`/archive`) sin cambios.
- `ArtifactBrowser.tsx` ya previsualiza `.md` con Mermaid y `stripMermaidConfig` (G46). Cambio mínimo: quitar la línea
  de front matter (`---\n{json}\n---`) antes de `marked.parse`.
- `RunOutputs.tsx`: sin botones por fichero (serían miles); enlace «Portada Markdown» a `docs/index.md` en el navegador
  de artefactos.
- **Fuera de alcance:** construir el sitio con `zensical build` en el job (Zensical no está en la imagen de runtime:
  dependencia y ADR nuevos). Queda en «Mejoras opcionales».

### G — Contrato, documentación y versión (W-10)

- `scripts/export_openapi.py` + `npm run gen:api` (cambian `DocumentationParams`, `TemplateOut.kind`, `RunDetailOut`).
- `docs/plan/ROADMAP.md` (sección «Después de la 1.0»), `docs/plan/UTIL_BBDD_GAPS.md` (G49), guía de documentación de
  usuario, `docs/adr/ADR-011` (adenda: tipo `trace`), `CHANGELOG.md`.

## HTTP contract

| Endpoint | Cambio | Errores |
|---|---|---|
| `POST /api/v1/projects/{id}/runs` (`documentation`) | params nuevos: `markdown`, `markdown_site_name`, `markdown_diagram_depth`, `trace_map`, `markdown_previous_run` | 422 `invalid_params` (sin formato, ejecución anterior no válida, plantilla de otro tipo) |
| `GET/POST/PATCH/DELETE` de plantillas (proyecto y globales) | `kind: "word" \| "excel" \| "trace"` | 415/422 existentes (extensión, tamaño, sintaxis) |
| `GET /api/v1/runs/{id}` | `has_diff: bool` | — |
| `GET /api/v1/runs/{id}/diff` | también para `documentation` con `changes.json` | 404 `diff_not_available`, 413 `diff_too_large` (existentes) |
| Errores del job | códigos nuevos `invalid_trace_map` y `invalid_previous` (mensaje de util_bbdd con las rutas sustituidas) | — |

## util_bbdd usage (verified signatures)

Verificado en el repo origen, tag `v5.3.0` (`2841111d`):

- `DatabaseDocumentation(manager, directorio_salida, fichero_salida, imprimir, formatos, headers_file,
  batch_window_seconds, schema, on_progress, cancel_token)` — sin cambios de firma; `formatos` admite `"markdown"`.
- `imprimir["markdown"]`: `max_diagram_depth` (2), `index_page_size`, `front_matter`, `column_anchors`,
  `catalog_json`, `llms_txt`, `llms_full_txt`, `mkdocs_yml`, `site_name`, `mermaid_js`, `trace_map`, `previous`
  (`docs/api/database_documentation.md` § «Documentación Markdown»; `PrintConfigManager._normalize_markdown`).
- Profundidad efectiva `min(grafo.max_depth, markdown.max_diagram_depth)`; diagramas si `grafo.enabled`
  (`include_diagrams`), con `MermaidRelationshipGraph`, sin Graphviz.
- Salida `<dir>/<nombre>/MARKDOWN/{manifest.json, mkdocs.yml, docs/…}`; staging (cancelación sin carpeta a medias).
- `_check_markdown_inputs` valida `trace_map` y `previous` **al construir** (antes de leer el catálogo, pero ya
  dentro de `with SyncDatabaseManager`).
- Mensajes de `DocumentationConfigError` con **ruta absoluta** del fichero en algunos casos (`_trace.py:105, 111`;
  `_changes.py:93`) → hay que sanearlos.
- `previous` admite la carpeta `MARKDOWN`, su `docs/` o su `catalog.json` (≤ 50 MB); mismo motor o error al generar
  (`_changes.py:164`).
- `changes.json` = `SchemaDiff.to_dict()` (`_changes.changes_json`).
- Progreso: fase `"markdown"`, un evento por tabla.

## Risks

1. **Wheel 5.3.0 no publicado** (bloquea A y, por tanto, todo).
2. Fuga de rutas del servidor en los mensajes de `DocumentationConfigError` (regla 5 / OWASP A01-A09).
3. Volumen: un `.md` por objeto → miles de filas `artifacts` por run y de entradas en el navegador; el
   `mermaid.min.js` (~3 MB) se copia en cada run y cuenta para la cuota (ADR-012).
4. El mapa se valida a fondo solo en el job (y tras conectar): un mapa con errores de esquema se descubre tarde.
5. Contenido del usuario (mapa, nombres de objetos) en Markdown que la SPA renderiza: depende del saneado actual de
   `ArtifactBrowser` (DOMPurify/`securityLevel: strict`) — se reutiliza, no se amplía.
6. Una documentación sin Graphviz era imposible con `graphs=true`; ahora solo-Markdown sí: cambia la condición de
   `graphviz_missing`.

## Test strategy

- **unit**: `build_imprimir` con y sin Markdown (bloque `markdown`, `mermaid_js`, `trace_map`, `previous`); la
  condición de Graphviz; `public_message` sin rutas; `trace_map_failed`; validación de subida `trace` (tamaño,
  UTF-8, TOML/JSON inválidos, extensión).
- **api**: lanzar `documentation` con `markdown` (validación de `markdown_previous_run`: otro proyecto, otra
  conexión, otro schema, no terminada, sin Markdown); CRUD de plantillas `trace`; `/diff` de una documentación;
  `has_diff`.
- **integration (SQLite, fuera del CI salvo que ya corra con SQLite)**: `formats=("markdown",)` → `docs/index.md`,
  `docs/catalog.json`, `mkdocs.yml` con `extra_javascript` si hay `UBW_MERMAID_JS`; artefactos registrados y en el
  ZIP; mapa inválido → `invalid_trace_map` con todos los errores y sin rutas; segunda documentación con la primera
  como anterior → `changes.json` legible por `/diff`; cancelación sin `outputs/markdown` a medias.
- **Vitest**: casilla Markdown muestra/oculta su grupo; selector de ejecución anterior; front matter fuera de la
  vista previa; visor de diferencias con `has_diff`; subida de mapa.
- **E2E (Playwright)**: documentación Markdown de la BD de ejemplo y apertura de la portada.
- Arquitectura: el test de capa anticorrupción sigue pasando (solo `integrations/util_bbdd` importa util_bbdd).
