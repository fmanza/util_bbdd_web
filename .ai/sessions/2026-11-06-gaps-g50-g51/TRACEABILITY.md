# TRACEABILITY

## Session metadata
- id: 2026-11-06-gaps-g50-g51
- fecha: 2026-11-06
- rama: develop
- skill: new_feature + version_closure
- fase: PLAN + AUDIT_PLAN (ola 11) → U-11 en util_bbdd (otra sesión) → W-11.0 a W-11.3 + VERSION → 1.13.0

## Prompt issued
1. «Huecos de util_bbdd: G50 y G51 siguen abiertos. PLAN Y AUDIT_PLAN, pregunta lo que necesites» (D11-1 a D11-4).
2. «Todo» (D11-5 a D11-8 y commit `docs(plan)`).
3. «La Ola 11 ya está implementada» y, a la pregunta del orden, «W-11 ahora como 1.13.0».

## Context supplied
- util_bbdd 5.3.0 y 5.4.0 (repo origen, solo lectura): `markdown_generator.py`, `_site.py`, `_writer.py`,
  `print_config_manager.py`, `documentation_orchestrator.py`, `docs/api/database_documentation.md`, CHANGELOG y la
  sesión `2026-11-06-gaps-g50-g51` de util_bbdd (T3/T4 verificados allí).
- Release `v5.4.0` de GitHub (wheel, `.sha256`, zip de documentación).

## AI output summary
- PLAN y AUDIT_PLAN (GO_CONDICIONAL) con D11-1 a D11-8; registro de la ola en `UTIL_BBDD_GAPS_PLAN.md` (`c6cb768`).
  T3 (zensical con el fichero ausente) no concluyente aquí; se dejó a U-11.1, que lo verificó.
- D6 de la sesión `2026-11-06-explorer-runs-lists` había movido la ola a 1.14.0; con 5.4.0 publicada, el usuario
  la adelantó a 1.13.0 (`d47d905`).
- W-11.0 `9f7e57e`, W-11.1 `ded2592`, W-11.2 `a56e54c`, W-11.3 `c9c247a` (registro en §6 del plan de huecos).
- Ajuste respecto del PLAN en W-11.2: sin índice, el endpoint devuelve `paths` con la lista vacía y el frontend
  conserva su deducción por rutas, en lugar de repetirla en el backend.
- Validación: backend 784 passed (no integración), frontend 186 passed, lint, typecheck, build, OpenAPI y
  `zensical build --strict`; F1 con util_bbdd 5.4.0 real y `zensical build --strict` de la carpeta con el Mermaid
  añadido como el ZIP.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN / AUDIT_PLAN | `.ai/sessions/2026-11-06-gaps-g50-g51/` | emitido y aprobado |
| W-11.1 | `backend/app/{jobs/operations/documentation.py, jobs/runner.py, workspace/layout.py, api/v1/runs.py, integrations/util_bbdd/documentation.py}` | completado |
| W-11.2 | `backend/app/domain/runs/markdown_pages.py`, `api/v1/runs.py`, `schemas_projects.py`; `frontend/src/features/runs/documentation/*`, `useRuns.ts` | completado |
| Docs | `UTIL_BBDD_GAPS.md`, `UTIL_BBDD_GAPS_PLAN.md`, `documentacion.md`, ADR-007, ROADMAP, CHANGELOG | completado |

## Directrices para Futuras IAs
- **[backend/Mermaid]**: desde la 1.13.0 una documentación Markdown no guarda `mermaid.min.js`; `run.json` → `markdown_mermaid.mode == "referenced"` hace que `download_archive` (`_archive_extras`) lo añada desde `UBW_MERMAID_JS` en `MARKDOWN_MERMAID_ARTIFACT`. Las ejecuciones anteriores tienen la copia como artefacto y no se duplica.
- **[backend/tests]**: `settings` está en caché (`get_settings`): para que el worker (subproceso) y la API vean el mismo `UBW_MERMAID_JS` hay que poner la variable de entorno **y** `monkeypatch.setattr(settings, "mermaid_js", …)` (`_use_mermaid` en `test_documentation_markdown.py`).
- **[backend/G51]**: `markdown_pages.load_pages` solo acepta `manifest.json` con `format == "util_bbdd.doc.markdown"` y `format_version >= 2`, ≤ 8 MB, y descarta páginas que no son artefactos `.md` registrados o con `section`/`role` desconocidos; cualquier otro caso → `source = "paths"` sin páginas.
- **[frontend/visor]**: con `source == "manifest"` el árbol usa `pagesFromIndex` (orden de util_bbdd, títulos); si no, `buildPages` (rutas). `objectName` quita el tipo del título solo en páginas de objeto fuera de la portada (`Tabla: X` → `X`).
- **[util_bbdd 5.4.0]**: en SQLite el título de la portada incluye la ruta del fichero de la BD (el nombre que util_bbdd da a la base de datos); no es nuevo (ya era el H1 de `index.md`), pero ahora también sale en el árbol.
- **[util_bbdd 5.4.0]**: con `mermaid_js_ref` y el fichero ausente, `zensical build --strict` y `mkdocs build --strict` no avisan y Material carga Mermaid 11 de unpkg (verificado en la sesión de util_bbdd).

## Veredicto final
Veredicto: CLOSED (1.13.0)
Pendientes al cierre:
- Sesión `2026-11-06-explorer-runs-lists` (explorador, eliminar ejecuciones, listas) → 1.14.0.
- Mermaid incrustado en el informe HTML de comparación (5,5 MB por informe): fuera de alcance; candidato a hueco aparte.
