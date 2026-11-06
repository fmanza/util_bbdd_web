# TRACEABILITY

## Session metadata
- id: 2026-11-06-doc-markdown
- fecha: 2026-11-06
- rama: develop
- skill: new_feature + audit_code + version_closure
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE (H1-H3 corregidos) + VERSION → 1.11.0

## Prompt issued
1. «Leer el fichero C:\Desarrollo\python\libs\util_bbdd\.ai\sessions\2026-11-05-doc-markdown\WEB_HANDOFF.md y preparar
   PLAN y AUDIT_PLAN»
2. «El wheel ya está. IMPLEMENT»
3. «Hazlo» (AUDIT_CODE)
4. «Hazlo» (corregir H1-H3 y VERSION)

## Context supplied
- `WEB_HANDOFF.md` de util_bbdd (W-1…W-10) y el repo origen `util_bbdd` en el tag `v5.3.0` (`2841111d`).
- `CLAUDE.md`, `.github/SHARED_INSTRUCTIONS.md`, prompts `new_feature`, `audit_code` y `version_closure`, agentes
  Plan Architect, Feature Implementer, Code Auditor, Frontend Reviewer y Version Closer.

## AI output summary
- PLAN y AUDIT_PLAN contrastados con el código (v1.10.1) y util_bbdd 5.3.0: `GO_CONDICIONAL`. El wheel 5.3.0 no estaba
  publicado (bloqueante); se detectaron la exigencia de Graphviz para solo Markdown y las rutas del servidor en los
  mensajes de `DocumentationConfigError`, que el traspaso no recogía.
- Decisiones abiertas sin respuesta del usuario → se aplicó la propuesta: un mapa inválido hace fallar la ejecución
  (`invalid_trace_map`); entrega única.
- IMPLEMENT por bloques A-G (ver `IMPLEMENT.md`): util_bbdd 5.3.0 (hash del lock = `.sha256` de la release),
  formato Markdown con carpeta completa y Mermaid local, Graphviz solo para Word/HTML, mapa como plantilla `trace`,
  comparación con la documentación anterior (copia de su `catalog.json`) y visor de diferencias, formulario genérico
  con `requires` y tipo `run`, vista previa sin front matter, contrato y cliente regenerados, guía, ADR-011, G49,
  ROADMAP y CHANGELOG.
- Medición T2: 500 tablas solo Markdown → 3,0 s, 511 artefactos, 2,9 s de registro, 2,8 MB.
- AUDIT_CODE: `APROBADO CON CONDICIONES` (H1 saneado de rutas demasiado amplio; H2 campos ocultos validados; H3
  anterior no comparable que se queda en el formulario; H4-H5 residuales). Corregidos H1-H3 con tests, más los tests
  recomendados 2 (anterior purgada antes de empezar, con mensaje propio «se purgó») y 5 (panel de plantillas).
- VERSION 1.11.0 sincronizada en `CHANGELOG.md`, `backend/pyproject.toml`, `backend/app/__init__.py`,
  `frontend/package.json` (+ lock), `backend/uv.lock`, `openapi/openapi.json`, `.env.example` y `.ai/product.md`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| REQUEST | `.ai/sessions/2026-11-06-doc-markdown/00_REQUEST.md` | emitido |
| PLAN | `.ai/sessions/2026-11-06-doc-markdown/PLAN.md` | emitido |
| AUDIT_PLAN | `.ai/sessions/2026-11-06-doc-markdown/AUDIT_PLAN.md` | `GO_CONDICIONAL` |
| IMPLEMENT | `backend/…`, `frontend/…`, `openapi/openapi.json`, `docs/…` · `IMPLEMENT.md` | completado |
| AUDIT_CODE | `.ai/sessions/2026-11-06-doc-markdown/AUDIT_CODE.md` | `APROBADO CON CONDICIONES` → condiciones cumplidas |
| VERSION | este fichero, `CHANGELOG.md` `[1.11.0]` | sin commit (no pedido) |

## Directrices para Futuras IAs
- **[util_bbdd]**: el formato Markdown deja `<dir>/<nombre>/MARKDOWN/{manifest.json, mkdocs.yml, docs/…}`; hay que
  mover la **carpeta entera** (como el HTML): mover solo los ficheros de primer nivel pierde `docs/`.
- **[util_bbdd]**: `markdown.trace_map` y `markdown.previous` se validan en el **constructor** de
  `DatabaseDocumentation` (ya dentro de `with SyncDatabaseManager`) y sus `DocumentationConfigError` incluyen la
  **ruta absoluta** del fichero; `markdown_input_error`/`public_message` (`integrations/util_bbdd/documentation.py`)
  los sanean. `TraceMap` es privado (G49).
- **[util_bbdd]**: `changes.json` de la documentación es `SchemaDiff.to_dict()`: lo lee `read_diff` sin cambios.
- **[util_bbdd]**: `mkdocs_yml` escribe `site_name` con `json.dumps` (sin inyección YAML); `md_text` escapa notas y
  etiquetas del mapa, y solo enlaza URL `http(s)`.
- **[backend]**: los diagramas del Markdown son de Mermaid: `GraphvizMissingError` solo si hay diagramas **y** Word o
  HTML (`GRAPHVIZ_FORMATS`).
- **[backend]**: el mapa de trazabilidad es el tipo `trace` de `document_templates` (cabe en `String(8)`; `trace_map`
  no cabría). Se guarda con su extensión (`stored_suffix`), porque util_bbdd elige TOML o JSON por ella; las copias en
  `inputs/` usan `Path(template.path).suffix`.
- **[backend]**: la documentación anterior se valida en `domain/runs/documentations.py` (mismo proyecto, alias y
  schema, `succeeded`, `catalog.json` registrado) **al encolar y en el worker**, y solo se copia su `catalog.json` a
  `inputs/previous/`.
- **[backend]**: `_ABSOLUTE_PATH` solo reconoce rutas tras el principio, un espacio, una comilla o un paréntesis; sin
  ese ancla, deforma rutas relativas, claves con `/` y URL (H1).
- **[frontend]**: el formulario genérico admite `requires` (el campo solo se muestra, valida y envía con ese booleano
  activo; al desactivarlo vuelve a su valor por defecto) y `type: "run"` (selector con `useSucceededRuns`, filtrado en
  el cliente por conexión, schema y Markdown). Los ocultos de tipo `template`/`run` se envían como `null`; el resto con
  `requires`, se omiten.
- **[tests]**: en `pytest.mark.parametrize` con valores de 1 MB, pon `ids=`: sin ellos, el id no cabe en
  `PYTEST_CURRENT_TEST` en Windows («environment variable is longer than 32767 characters»).
- **[tests]**: el nombre accesible de un `Switch` de Mantine incluye la descripción: búscalo con `name: /^Etiqueta/`.
- **[entorno]**: con este banco local, los tests de integración `[sqlserver]` fallan al conectar a `127.0.0.1`
  aunque el contenedor `util_bbdd_bench_mssql` esté *healthy*. Es del entorno: también fallan tests no tocados.
- **[herramientas]**: `Path.write_text` en Windows escribe CRLF; usa `newline="\n"` en los scripts de edición o
  normaliza después (git avisa con «CRLF will be replaced by LF»).

## Veredicto final
Veredicto: CLOSED (1.11.0 lista para commit y release; commit no ejecutado: no se pidió)
Pendientes al cierre:
- Commit y tag `v1.11.0` cuando el usuario lo pida (`docs/guides/publicar_version.md`).
- `/api/health` con la imagen nueva: no verificado (no se reemplazó el despliegue local en marcha).
- G49 (validador público del mapa) en util_bbdd; H4 (selector limitado a 50) y H5 (comparación por alias) residuales.
- Mejora opcional: sitio Markdown con `zensical build` servido por URL firmada.
