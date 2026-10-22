# TRACEABILITY

## Session metadata
- id: 2026-10-22-fase5
- fecha: 2026-10-22
- rama: develop
- skill: phase
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION (Fase 5 del ROADMAP)

## Prompt issued
`/phase 5: documentación (Word, Excel y HTML) y grafos de relaciones.` Respuestas: alcance completo, `marked` como
renderizador de Markdown, sin mejoras. Tras AUDIT_PLAN: «IMPLEMENT, pregunta lo necesario» → sitio HTML en origen
opaco con scripts; Oracle aceptado con aviso.

## Context supplied
- Ver `00_CONTEXT_SNAPSHOT.md`.

## AI output summary
- PLAN y AUDIT_PLAN: firmas de util_bbdd verificadas; hallazgos G21–G22; `GO_CONDICIONAL` con dos decisiones, que
  tomó el usuario.
- Backend:
  - `operations.py`: `DocumentationParams` y `RelationshipGraphParams`, con secciones (`ubw_group`), desplegables
    (`Literal` → `options`), alias `schema` y nombres de objeto restringidos (`OBJECT_NAME_PATTERN`).
  - Capa anticorrupción `integrations/util_bbdd/documentation.py`: `with_schema` (schema por motor; Oracle solo el
    del usuario), `build_imprimir`, `generate_documentation` (salida recolocada en `outputs/{word,excel}` y
    `outputs/html/documentacion`; `work/` siempre se borra) y `generate_graphs`.
  - Jobs `jobs/operations/documentation.py` con errores saneados (`invalid_params`, `graphviz_missing`,
    `no_relations`, códigos de `classify`); `JobContext.connection_params`.
  - ADR-007: `GET /runs/{id}/site/{token}/{ruta}` con token HMAC (usuario, run, caducidad), comprobación de
    membresía en cada petición, solo artefactos `html` registrados, CSP `sandbox allow-scripts` sin
    `allow-same-origin` y `Referrer-Policy: no-referrer`; `site_url` en el detalle.
  - Corregido: la vista previa de un PNG de `graphs` se servía como `text/html`.
  - Graphviz en el CI y en `backend-dev`.
- Frontend: formulario por secciones (`Fieldset`) con `NativeSelect` para opciones, operación y conexión; aviso de
  Oracle; `RunOutputs` (sitio en iframe, abrir en pestaña nueva, Word/Excel, galería de grafos); Markdown con
  `marked` cargado bajo demanda en `iframe srcdoc sandbox=""` con CSP; ficheros del sitio ocultos en la lista.
- AUDIT_CODE (hallazgos corregidos durante la auditoría): `schema`/`table` aceptaban cualquier texto (ahora
  identificadores); `work/` quedaba en el run si util_bbdd fallaba (ahora `finally`).
- Tests:
  - Backend: 43 nuevos (400) — util_bbdd real sobre SQLite (3 formatos abiertos como ZIP, grafos SVG/PNG, errores),
    URL firmada (anónimo OK, token manipulado, caducado, de otro usuario, usuario desactivado, *traversal*,
    otro run), parámetros y capa de integración.
  - Integración: 11 nuevos (37) contra PostgreSQL, MySQL, MariaDB, SQL Server y Oracle.
  - Vitest: 3 nuevos (63). E2E: `documentation.spec.ts`, que comprueba en Chromium que el sitio tiene
    `origin === 'null'` y no lee la cookie ni el documento de la SPA.
- AUDIT_CODE:
  - Backend local y en `backend-dev` (Linux + Graphviz): ruff, mypy, pytest y contrato OK.
  - Frontend: format, lint, tsc, Vitest (63) y build OK; bundle principal de 485 kB; `marked` en su propio chunk
    (45 kB).
  - Imagen 0.6.0: web y worker sanos; Playwright 13/13, y 26/26 con `--repeat-each=2 --workers=2`.
  - Salidas en `build/logs/fase5_*.txt`.
- VERSION: 0.6.0, CHANGELOG, ROADMAP, guías, ADR-007, GAPS, `.ai/product.md`, sesión e `INDEX.md`.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | conversación de la sesión | emitido (GO_CONDICIONAL, condiciones resueltas) |
| Capa anticorrupción | `backend/app/integrations/util_bbdd/documentation.py` | completado |
| Jobs y API | `backend/app/jobs/operations/documentation.py`, `backend/app/api/v1/runs.py`, `backend/app/core/security.py` | completado |
| Tests | `backend/tests/{unit/test_documentation_units.py,api/test_documentation.py,integration/test_bench_documentation.py}` | completado |
| Frontend | `frontend/src/features/runs/{LaunchRunModal,RunOutputs,ArtifactBrowser}.tsx` | completado |
| E2E | `frontend/e2e/documentation.spec.ts` | ejecutado |
| Docs | `docs/guides/documentacion.md`, `docs/adr/ADR-007-sitio-html-aislado.md`, GAPS, CHANGELOG, ROADMAP | completado |

## Directrices para Futuras IAs
- **[sitio-html]**: el sitio de util_bbdd solo se sirve por `/runs/{id}/site/{token}/…` (ADR-007). Nunca hay que añadir `allow-same-origin` al iframe ni quitar `sandbox` de la CSP: con scripts, eso le daría acceso a la API como el usuario. Un iframe con origen opaco **no envía** la cookie `SameSite=Lax`; por eso la URL lleva el token.
- **[util_bbdd-schema]**: `DatabaseDocumentation` y `GraphvizRelationshipGraphExt` sacan el schema de los `conn_params` (`schema` en PostgreSQL, SQL Server y HSQLDB; `database` en MySQL/MariaDB). Oracle usa siempre el usuario de la conexión (G21, G22). Hay que pasar por `with_schema`.
- **[util_bbdd-doc]**: `imprimir` trae todas las secciones a `False` por defecto. La salida va en `<dir>/<fichero_salida>/{WORD,EXCEL,HTML}` y hay que usar siempre `batch_window_seconds=0` y un `fichero_salida` explícito (G2). `plantilla_word` es una ruta del servidor: no se expone.
- **[nombres-objeto]**: todo nombre de schema o tabla que llegue a util_bbdd desde un formulario usa `OBJECT_NAME_PATTERN`, porque util_bbdd puede interpolarlo en SQL de catálogo.
- **[graphviz]**: los tests de documentación y grafos llaman a `dot` (en el CI se instala por apt; en local se saltan si no está). Los nombres de fichero de los grafos llevan el prefijo `graphviz_ext_`.
- **[formulario-operaciones]**: el formulario se genera del modelo Pydantic: `json_schema_extra={"ubw_group": …}` crea secciones y un `Literal` crea un desplegable. Las etiquetas van en `runs.params.<op>.<param>`, `runs.groups.*` y `runs.options.*`. En jsdom, solo `NativeSelect` es comprobable.
- **[e2e-cola]**: el admin E2E tiene el límite de 5 ejecuciones en cola o en curso. Con `--repeat-each=2`, hay que usar `--workers=2` o aparece «Demasiadas ejecuciones en cola». Tras lanzar, se espera `toHaveURL(/\/runs\//)` antes de buscar el estado: la lista del proyecto también muestra «Correcta».

## Veredicto final
Veredicto: CLOSED (Fase 5 cumplida; DoD común y de la fase verificadas contra SQLite real, 5 motores bench y E2E)
Pendientes al cierre:
- Riesgos residuales:
  - Una URL del sitio ya emitida sigue sirviendo hasta caducar aunque se cierre la sesión (sí deja de servir si se
    quita al usuario del proyecto o se desactiva).
  - Documentar schemas muy grandes puede acercarse a `UBW_JOB_TIMEOUT_SECONDS` (sin progreso fino, G1).
- El CI no ejecuta Playwright ni la integración.
- Sin commit (pendiente de petición). Siguiente paso: `/phase 6` (comparación de esquemas).
