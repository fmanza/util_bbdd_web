# IMPLEMENT — Tarjetas de salida de la documentación (Word, Excel, HTML, Markdown)

Lanzado por el usuario el 2026-11-06 (`/new-feature`, PLAN y AUDIT_PLAN aprobados con GO_CONDICIONAL). Restricciones:
una versión 1.12.0 con dos commits `feat` (paso 1 y paso 2), sin migración, enmienda de ADR-007, sin dependencias
nuevas. **Decisión del usuario durante IMPLEMENT**: `dompurify` se declara dependencia directa del frontend fijada a
3.4.17, la versión que ya instalaba Mermaid (el lockfile solo añade la línea de la raíz; ningún paquete nuevo).

## Verificaciones previas (pedidas antes de implementar)

| Verificación | Resultado (ejecución real del contenedor, 630 tablas, run `01M6REV4…`) |
|---|---|
| Mensaje de los tres errores de la vista previa | `mermaid.min.js` 5,5 MB, `catalog.json` 3,6 MB y `llms-full.txt` 12,4 MB superan los 2 MB → la API responde **413** con *problem details*, pero `useArtifactText` lanzaba un `Error` plano y el usuario veía el genérico **«Se ha producido un error · Inténtalo de nuevo más tarde.»**. Corregido: lanza `ApiError` con el *problem* (y sin reintentos, por ser 4xx) |
| ZIP HTML desde `file://` | Chromium (Playwright) abre `index.html` desde disco: iframe `detailFrame`, navegación del índice, buscador y resaltado SQL sin errores de consola. Documentado en la guía. Firefox no comprobado |

## Condiciones del AUDIT_PLAN

| Condición | Resultado |
|---|---|
| F1 tarjeta por formato **pedido** | `documentationFormats`: pedido (`params`, con los valores por defecto del formulario) en una ejecución correcta, o con ficheros; sin ficheros → «Sin ficheros» |
| T2 test de contrato (obligatorio con G51 abierto) | `test_documentation_archive_by_format_preview_rules_and_page_layout`: páginas solo en la raíz de `docs/` o en `tables`, `views`, `routines`, `database`; índices por letra; profundidad ≤ 1 |
| T5 mensajes del iframe | `event.source === iframe.contentWindow` + `navHref` (`{type: 'ubw-md-nav', href: string}`, ≤ 2048) |
| T6 resolución de rutas | `resolveLink`: `./`, `../`, `%xx`, sin salir de `docs/`, sin `\`, solo artefactos registrados |
| T7 nonce + DOMPurify antes del script | Nonce de 128 bits por render; DOMPurify sobre el HTML final (con los SVG); el script se añade después |
| S1 (bloqueante) | `sandbox="allow-scripts"` sin `allow-same-origin`; CSP con nonce, `connect-src 'none'`, `form-action 'none'`, `base-uri 'none'`; ADR-007 enmendado. Comprobado en Chromium: origen `null`, un `<script>` y un `onclick` inyectados **sin limpiar** quedan bloqueados por la CSP |
| S2 SVG | `USE_PROFILES {html, svg, svgFilters}` + `foreignObject` como punto de integración HTML (Mermaid 12 dibuja ahí 273 etiquetas en una tabla real; sin él se pierden todas). Test con carga maliciosa dentro de `foreignObject` |
| S3 / D4 externos | Modal con la URL completa; `window.open(url, '_blank', 'noopener,noreferrer')`; test con `javascript:`, `data:`, `file:` y `//host` |

## Paso 1 — tarjetas, ZIP por formato y vista previa

- **Backend**: `runs.py` (`_previewable` por extensión en `markdown`, `download_archive` con `format: Literal`,
  `_detail` con `warnings_by_format` y `templates_applied` leídos de `run.json`), `schemas_projects.py`
  (`RunDetailOut` +2 campos opcionales), `jobs/operations/documentation.py` (avisos agrupados por formato),
  `integrations/util_bbdd/documentation.py` (`_Outcome.by_format`, `warnings_by_format` en el resumen),
  `jobs/runner.py` (`warnings_by_format` en `run.json`, solo si hay). *Fuera de las rutas del pedido, justificados*:
  la integración es donde nacen los avisos de plantilla y el runner es quien escribe `run.json`.
- **Contrato**: `openapi/openapi.json`, `frontend/src/api/schema.d.ts`.
- **Frontend**: `documentation/DocumentationOutputs.tsx` (nuevo), `RunOutputs.tsx` (delegación), `RunDetailPage.tsx`
  (cabecera sin los avisos de formato), `ArtifactBrowser.tsx` (oculta `outputs/markdown/documentacion/**`),
  `useRuns.ts` (`archiveUrl(runId, format?)`, `isMarkdownDocFile`, `ApiError` en la vista previa), i18n.

## Paso 2 — visor Markdown M2

- `documentation/markdownNav.ts` (árbol y `resolveLink`, puras), `documentation/markdownFrame.ts` (DOMPurify, nonce,
  CSP, puente, `navHref`), `documentation/MarkdownViewer.tsx` (árbol con sección, letra y buscador; iframe; historial
  propio; `?md=`; avisos de descarga y enlace roto; modal externo), `package.json` (`dompurify`), i18n.

## Documentación

Guía `documentacion.md` (sección «Resultados: una tarjeta por formato»; corregido «3 MB» → 5,5 MB de Mermaid),
ADR-007 (enmienda 2026-11-06), ROADMAP, CHANGELOG (`[Unreleased]`).

## Validación

| Comando | Resultado |
|---|---|
| `ruff format --check`, `ruff check`, `mypy` | OK (122 ficheros) |
| `pytest -m "not integration"` | 778 passed, 2 skipped |
| `pytest` completo | 850 passed; 19 fallos/errores, **todos** `tests/integration` contra el SQL Server del bench, que rechaza la conexión (`TDS server is unavailable`, 10061): entorno, no este cambio |
| `export_openapi.py --check` | OK |
| `npm run format:check`, `lint`, `typecheck`, `build` | OK |
| `npm test` | 182 passed (24 ficheros). Un fallo intermitente en `auth.test.tsx` («cierra sesión…», `findBy` de 1 s) con la máquina cargada; pasa solo y en tres ejecuciones completas seguidas |
| `zensical build --strict` | OK |
| Chromium (Playwright, arnés con los módulos reales) | Ver S1/S2 y verificaciones previas |
