# TRACEABILITY

## Session metadata
- id: 2026-11-06-doc-output-cards
- fecha: 2026-11-06
- rama: develop
- skill: new_feature + audit_code + version_closure
- fase: PLAN + AUDIT_PLAN (sesión anterior del mismo día) + IMPLEMENT (pasos 1 y 2) + AUDIT_CODE + VERSION → 1.12.0

## Prompt issued
1. Petición de PLAN y AUDIT_PLAN ([00_REQUEST.md](00_REQUEST.md)); decisiones D1-D4 del usuario recogidas en el PLAN.
2. «/new-feature — Sesión: .ai/sessions/2026-11-06-doc-output-cards/ (PLAN y AUDIT_PLAN aprobados el 2026-11-06;
   GO_CONDICIONAL). No rehagas el PLAN: pasa directamente a IMPLEMENT cumpliendo sus condiciones. […] Restricciones:
   una sola versión 1.12.0 con dos commits feat (paso 1: tarjetas, ZIP y vista previa; paso 2: visor M2); sin
   dependencias nuevas; sin migración; enmendar ADR-007. Antes de implementar: verificar el mensaje real de los tres
   errores de la vista previa y si el ZIP HTML se abre desde file://»
3. DOMPurify: «Declararla directa (Recomendado)».
4. «si» (hacer los dos commits `feat`).
5. «version-closure: subir la versión a 1.12.0, pasar el CHANGELOG de [Unreleased] a [1.12.0], crear el
   TRACEABILITY.md de la sesión y hacer el commit release» y «sube también los cambios pendientes».

## Context supplied
- `CLAUDE.md`, `.github/SHARED_INSTRUCTIONS.md`, prompts `new_feature` y `version_closure`, agentes Feature
  Implementer y Version Closer, `sync.instructions.md`.
- [PLAN.md](PLAN.md), [AUDIT_PLAN.md](AUDIT_PLAN.md); ejecución real de documentación del contenedor
  `util_bbdd_web-web-1` (630 tablas, 3 777 artefactos) para las verificaciones previas.

## AI output summary
- Verificaciones previas: los tres ficheros superan 2 MB → 413 de la API mostrado como error genérico por el
  frontend; el ZIP HTML abre desde `file://` en Chromium (Playwright).
- Paso 1 (`6cd732b`): ZIP por formato, vista previa por extensión en `markdown`, `warnings_by_format` y
  `templates_applied`, tarjetas por formato, *Artefactos* sin la carpeta Markdown, `ApiError` en la vista previa.
- DOMPurify no era dependencia directa (solo transitiva de Mermaid): se preguntó y se declaró 3.4.17.
- Se comprobó en Chromium que prohibir `foreignObject` borra las etiquetas de los diagramas de Mermaid 12; se admite
  como punto de integración HTML (`HTML_INTEGRATION_POINTS`), con test de carga maliciosa.
- Paso 2 (`e5d6a03`): `markdownNav.ts`, `markdownFrame.ts`, `MarkdownViewer.tsx`; arnés en Chromium con los módulos
  reales (origen opaco, puente, anclas, CSP que bloquea script y `onclick` inyectados sin limpiar).
- AUDIT_CODE: APROBADO CON CONDICIONES; corregido C1 (`templates_applied` sin `applied` = no aplicada).
- Los dos commits se separaron reconstruyendo el estado del paso 1 y validándolo aparte (165 tests frontend).
- VERSION: 1.12.0 en los ficheros de `sync.instructions.md` (+ `uv.lock`, OpenAPI, `.env.example`), `product.md`,
  `INDEX.md`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN / AUDIT_PLAN | `.ai/sessions/2026-11-06-doc-output-cards/` | emitido (commit `9e1d5c5`) |
| IMPLEMENT | [IMPLEMENT.md](IMPLEMENT.md); `backend/app/api/v1/runs.py`, `schemas_projects.py`, `jobs/operations/documentation.py`, `jobs/runner.py`, `integrations/util_bbdd/documentation.py`; `frontend/src/features/runs/{RunOutputs,RunDetailPage,ArtifactBrowser,useRuns}`, `documentation/*` | completado (`6cd732b`, `e5d6a03`) |
| AUDIT_CODE | [AUDIT_CODE.md](AUDIT_CODE.md) | APROBADO CON CONDICIONES |
| Docs | `docs/guides/documentacion.md`, `docs/adr/ADR-007-sitio-html-aislado.md`, `docs/plan/ROADMAP.md`, `CHANGELOG.md` | completado |
| VERSION | este fichero; versión 1.12.0 | completado |

## Directrices para Futuras IAs
- **[frontend/vista previa]**: `useArtifactText` debe lanzar `ApiError` con el *problem details*; un `Error` plano hace que `ErrorAlert` muestre «Se ha producido un error» y oculta el 413/415 de la API.
- **[backend/vista previa]**: en el tipo `markdown` solo las rutas `.md` son `previewable` (`MARKDOWN_PREVIEW_SUFFIXES` en `api/v1/runs.py`); el tipo guardado (`_kind`, por carpeta) no se cambia para no migrar `artifacts`.
- **[frontend/seguridad]**: Mermaid 12 dibuja las etiquetas de los diagramas como HTML en `<foreignObject>`; DOMPurify las borra salvo con `ADD_TAGS: ['foreignObject']` y `HTML_INTEGRATION_POINTS: { foreignobject: true }` (`markdownFrame.ts`).
- **[frontend/seguridad]**: el iframe del visor Markdown tiene origen opaco (`event.origin === "null"`): los mensajes se validan por `event.source === iframe.contentWindow` y con `navHref`; los enlaces solo se resuelven contra artefactos registrados (`resolveLink`).
- **[frontend/tests]**: jsdom no ejecuta el script de un `srcdoc`; el puente del visor se prueba simulando `MessageEvent` con `source = iframe.contentWindow`, y su comportamiento real solo en navegador (Playwright).
- **[util_bbdd 5.3.0]**: las páginas Markdown están en `docs/` y en `docs/{tables,views,routines,database}/` (un nivel), con índices `index.md` e `index-<letra>.md`; las anclas de columna son `<a id="col-…">`. Lo fija `test_documentation_archive_by_format_preview_rules_and_page_layout` mientras G51 siga abierto.
- **[backend/avisos]**: los avisos de la documentación se guardan agrupados en `run.json` → `warnings_by_format` (`word`, `excel`, `markdown`) además de la lista plana `warnings`; las ejecuciones anteriores a la 1.12.0 solo tienen la lista y la cabecera los muestra todos.
- **[tests]**: `pytest` sin `-m "not integration"` incluye `tests/integration` contra el bench; si el SQL Server del bench no responde dan 19 fallos/errores ajenos al cambio.
- **[frontend/tests]**: `auth.test.tsx` «cierra sesión con la cabecera CSRF de la cookie» falla de forma intermitente con la máquina cargada (`findBy` de 1 s); pasa al repetir.

## Veredicto final
Veredicto: CLOSED (1.12.0)
Pendientes al cierre:
- Prueba manual del PLAN § 8 con la app reconstruida (documentación Markdown grande: tiempos del árbol y de la primera página, enlaces y anclas, ZIP Markdown con `zensical build`), condición de AUDIT_CODE.
- ZIP HTML desde `file://` en Firefox.
- R1 (ancla en la misma página no actualiza `?md=`), R5 (títulos sin `id`); G50 y G51 abiertos en util_bbdd.
- Test intermitente de `auth.test.tsx`.
