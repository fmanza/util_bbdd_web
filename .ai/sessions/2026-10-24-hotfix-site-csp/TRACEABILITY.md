# TRACEABILITY

## Session metadata
- id: 2026-10-24-hotfix-site-csp
- fecha: 2026-10-24
- rama: develop
- skill: hotfix
- fase: análisis + PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
Pruebas manuales de la documentación: «La visualización en HTML sale bloqueada el panel de información en local, en
todas las opciones»; «Abrir en pestaña nueva, bloquea la conexión desde local»; con `table_columns` a true, en Word no
se ven las columnas en el grafo y en HTML no se ve el grafo. «Analizar la situación actual». Tras el análisis: «si»
(`/hotfix` de la CSP) e «IMPLEMENT» tras AUDIT_PLAN.

## Context supplied
- Ejecución real `01M5PGBXCM9RZCM4495DZWFM5F` (MariaDB, schema `pruebas_util`, 3 tablas sin FK) copiada del volumen
  `util_bbdd_web_workspace` del stack desplegado.
- Plantillas y renderers de util_bbdd 4.0.0 (repo origen en v4.0.1, sin diferencias en `doc/` ni `analysis/`).

## AI output summary
- Análisis: el `index.html` de util_bbdd muestra el detalle en `<iframe name="detailFrame">`. Reproducido en Chromium
  (Playwright) sirviendo el sitio con la `SITE_CSP` original:
  - `Framing … violates "default-src 'none'"` (no había `frame-src`);
  - con `frame-src 'self'`, `Framing … violates "frame-ancestors 'self'"`; también con `frame-ancestors *`.
- Grafo (fuera de este hotfix): `table_columns` no interviene. Word dibuja el nodo con «Sin columnas visibles»
  (modo `relations` y tablas sin FK); el HTML omite la sección si la tabla no tiene relaciones.
- PLAN/AUDIT_PLAN: `GO`. IMPLEMENT:
  - `backend/app/api/v1/runs.py`: `SITE_CSP` con `frame-src 'self'` y sin `frame-ancestors`; `SITE_ROOT_CSP` con
    `frame-ancestors 'self'`; `_site_csp(path)` elige según la ruta;
  - tests: `test_site_csp_lets_the_index_frame_its_detail_pages` (unit, sin Graphviz) y cabeceras de
    `tables/pedidos.html` en `test_site_is_served_by_signed_url_only`; ambos fallaban antes del fix;
  - E2E: `documentation.spec.ts` navega al detalle; `fixtures.ts` no ignora violaciones `Framing …`;
  - ADR-007 (enmienda 2026-10-24) y CHANGELOG (`Fixed`).
- Validación: ruff format/check, mypy, `export_openapi.py --check`, pytest (551 passed, 85 skipped), format:check,
  lint, typecheck, Vitest (105 passed), build y `zensical build --strict`. Navegación verificada en Chromium con las
  CSP exactas de `_site_csp`. **E2E no ejecutada**: el stack en marcha se despliega desde otra carpeta y no había
  credenciales de admin E2E.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Fix | `backend/app/api/v1/runs.py` | completado |
| Tests | `backend/tests/unit/test_documentation_units.py`, `backend/tests/api/test_documentation.py` | en verde |
| E2E | `frontend/e2e/documentation.spec.ts`, `frontend/e2e/fixtures.ts` | sin ejecutar |
| ADR | `docs/adr/ADR-007-sitio-html-aislado.md` | enmendado |
| Logs | `build/logs/hotfix-site-csp-*.txt` | generados |

## Directrices para Futuras IAs
- **[sitio-html]**: el `index.html` de util_bbdd carga el detalle en `<iframe name="detailFrame">`; la CSP del sitio
  necesita `frame-src 'self'`.
- **[sitio-html]**: ningún valor de `frame-ancestors` (ni `'self'` ni `*`) admite un ancestro con origen opaco; por eso
  solo el índice raíz (`<carpeta>/index.html`, `_site_csp`) lleva `frame-ancestors 'self'`.
- **[e2e]**: comprobar un texto de la barra lateral no prueba el sitio; hay que navegar al `detailFrame`. Las
  violaciones `Framing …` no se filtran en `fixtures.ts`.
- **[documentación]**: el grafo de la documentación ignora `table_columns`; usa `grafo.show_columns` y
  `grafo.columns.{mode,max_items,show_data_types}` (por defecto `relations`), que la web aún no expone.
- **[documentación]**: util_bbdd 4.0.0 omite el diagrama HTML de las tablas sin relaciones y Word las dibuja solas
  (hueco pendiente de registrar como G38).

## Veredicto final
Veredicto: GO_CONDICIONAL
Pendientes al cierre:
- Ejecutar la E2E `documentation.spec.ts` contra un stack con este código y probar el sitio a mano en Firefox.
- `/new-feature`: opciones de columnas del grafo en la documentación y registrar G38 en `UTIL_BBDD_GAPS.md`.
