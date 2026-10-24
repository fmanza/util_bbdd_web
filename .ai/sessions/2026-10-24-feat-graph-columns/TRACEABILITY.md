# TRACEABILITY

## Session metadata
- id: 2026-10-24-feat-graph-columns
- fecha: 2026-10-24
- rama: hotfix/site-csp (sin commit; cambios en el árbol de trabajo)
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
`/new-feature` para elegir qué columnas muestra el grafo de la documentación (hoy solo las de relación, y por eso
Word sale con «Sin columnas visibles»), y registrar G38: el HTML omite el diagrama de las tablas sin relaciones y Word
no. Tras AUDIT_PLAN: «IMPLEMENT», sin responder a las dos decisiones; se aplicaron las recomendadas
(`relations_first` por defecto y mantener el stack E2E aislado).

## Context supplied
- Análisis previo de la sesión `2026-10-24-hotfix-site-csp` (ejecución `01M5PGBXCM9RZCM4495DZWFM5F`).
- util_bbdd 4.0.0: `PrintConfigManager.normalize` (`grafo.show_columns`, `grafo.columns.{mode,max_items,
  show_data_types}`), `build_graph_generator_from_options` y `GraphvizRelationshipGraphExt._select_columns_for_table`.

## AI output summary
- PLAN/AUDIT_PLAN: `GO_CONDICIONAL` (valor por defecto y stack E2E pendientes de decisión).
- Backend:
  - `domain/runs/operations.py`: `graph_columns`, `graph_max_columns` (1–50) y `graph_data_types` en
    `DocumentationParams`, grupo `graphs`;
  - `integrations/util_bbdd/documentation.py`: `GraphColumns`, `_GRAPH_COLUMN_MODE` y `build_imprimir`, que añade
    `grafo.show_columns` y `grafo.columns`.
- Frontend: etiquetas en `i18n/es/features.json` (tres parámetros y la opción `relations_first`); el formulario es
  genérico.
- Tests:
  - unitarios de la traducción a `imprimir`, de los valores por defecto y de los rechazos;
  - API con Graphviz: `clientes.nombre` sale con `relations_first` y no con `relations`;
  - Vitest: opción por defecto, etiqueta y envío de `graph_columns`.
- Documentación: G38 en `UTIL_BBDD_GAPS.md`, sección «Columnas en el diagrama» en `docs/guides/documentacion.md`,
  CHANGELOG (`Added`).
- Validación: ruff, mypy, `export_openapi.py --check` (contrato sin cambios: `params` es libre), pytest (560 passed,
  85 skipped), format:check, lint, typecheck, build, Vitest (105 passed), `zensical build --strict` y E2E en el stack
  aislado `ubw_e2e` reconstruido (19 passed, 2 skipped). Word de una tabla SQLite sin FK: muestra sus columnas.
- Ampliación pedida tras el cierre («añadir “Primero las de relación” también al grafo de relaciones»):
  `RelationshipGraphParams.column_mode` y `GraphOptions.column_mode` admiten `relations_first` (por defecto sigue
  `relations`); `generate_graphs` traduce con `_GRAPH_COLUMN_MODE`. Test de API con los cuatro modos sobre
  `clientes`; guía y CHANGELOG. Validación repetida completa: pytest 564 passed (85 skipped), Vitest 105 passed,
  `zensical build --strict` y E2E en `ubw_e2e` reconstruido (19 passed, 2 skipped).

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| IMPLEMENT | `backend/app/domain/runs/operations.py`, `backend/app/integrations/util_bbdd/documentation.py` | completado |
| i18n | `frontend/src/i18n/es/features.json` | completado |
| Tests | `backend/tests/unit/test_documentation_units.py`, `backend/tests/api/test_documentation.py`, `frontend/src/features/runs/documentation.test.tsx`, `frontend/src/test/fixtures_runs.ts` | en verde |
| Docs | `docs/plan/UTIL_BBDD_GAPS.md` (G38), `docs/guides/documentacion.md`, `CHANGELOG.md` | completado |
| Logs | `build/logs/feat-graph-columns-*.txt` | generados |

## Directrices para Futuras IAs
- **[grafos]**: el `compact` de util_bbdd es «primero las columnas de relación y luego el resto hasta `max_columns`»;
  en la web `compact` significa «Sin columnas» (`runs.options.compact` y `show_columns = mode != "compact"` en
  `generate_graphs`). La documentación y el grafo de relaciones exponen el `compact` de util_bbdd como
  `relations_first` (`_GRAPH_COLUMN_MODE`).
- **[grafos]**: con `relations_first`, las columnas de relación no se recortan por `max_columns`; solo se rellena con
  el resto hasta ese máximo.
- **[documentación]**: `table_columns` controla la tabla de columnas del documento, no los diagramas; los diagramas
  dependen de `graph_columns`.
- **[documentación]**: los relanzamientos de ejecuciones anteriores a esta versión toman `relations_first` (sus
  `params` no tienen el campo) y sus diagramas pueden mostrar más columnas que el original.

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- G38 abierto en util_bbdd.
