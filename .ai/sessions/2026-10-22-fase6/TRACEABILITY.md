# TRACEABILITY

## Session metadata
- id: 2026-10-22-fase6
- fecha: 2026-10-22
- rama: develop
- skill: phase
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION (Fase 6 del ROADMAP)

## Prompt issued
`/phase 6`. Respuestas: alcance completo, mejora de evolución incluida, `diff` como visor de texto. Tras AUDIT_PLAN:
«IMPLEMENT, pregunta lo que necesites» → Mermaid del CDN bloqueado y, al comprobar que rompía el informe, sustituto
local.

## Context supplied
- Ver `00_CONTEXT_SNAPSHOT.md`.

## AI output summary
- PLAN y AUDIT_PLAN: firmas verificadas; hallazgos G23–G24; `GO_CONDICIONAL` con el schema de Oracle por verificar.
- Verificación en bench: en Oracle, el Inspector espera el nombre normalizado (`bench`), y un schema en minúsculas
  mal resuelto daba «Sin diferencias». Se resuelve contra `get_schema_names()` (exacto o única coincidencia sin
  mayúsculas) y, si no existe, la ejecución falla con el lado.
- Backend:
  - `integrations/util_bbdd/compare.py`: `Side`, `resolve_schema`, `relabel` (G23), `diff_to_dict` (G24),
    `localize_mermaid` (G25), `compare_schemas` e informes con nombre fijo (HTML en `outputs/html/comparacion/`).
  - `CompareParams` y la operación `compare`; job `jobs/operations/compare.py` con errores por lado; tipo de
    artefacto `diff`.
  - `domain/runs/diff.py` (`load_diff`, `leaf_items`, `evolution`) y endpoints `/runs/{id}/diff` y
    `/runs/{id}/diff/evolution`.
- Frontend: `features/runs/compare/` (`DiffViewer`, `DefinitionDiff` + `diffRows`, `DiffEvolution`, `useDiff`);
  `RunOutputs` con informes de comparación y aviso del script SQL; i18n `diff.*`.
- Hallazgo durante IMPLEMENT: bloquear Mermaid no solo quitaba el diagrama; abortaba todo el script del informe.
  Se informó al usuario, que eligió el sustituto local.
- Tests:
  - Backend: 28 nuevos (428), con dos SQLite reales (incluye que ningún artefacto lleve la ruta del servidor) y
    evolución con cambios reales en el destino.
  - Integración: 6 nuevos (43) con los 5 motores, Oracle con el schema en minúsculas, y PostgreSQL contra MySQL.
  - Vitest: 5 nuevos (68). E2E: `compare.spec.ts` (visor, informe con el sustituto en origen opaco, evolución) con
    `e2e/fixtures/tienda_v2.sql`.
- AUDIT_CODE:
  - Backend local y en `backend-dev`: ruff, mypy, pytest (428) y contrato OK.
  - Frontend: format, lint, tsc, Vitest (68) y build OK; bundle principal de 488 kB; `diff` en un chunk de 8 kB.
  - Imagen 0.7.0 sana; Playwright 28/28 con `--repeat-each=2 --workers=2`.
  - Salidas en `build/logs/fase6_*.txt`.
- VERSION: 0.7.0, CHANGELOG, ROADMAP, guía, ADR-007 (nota), GAPS, `.ai/product.md`, sesión e `INDEX.md`.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | conversación de la sesión | emitido (GO_CONDICIONAL, condición verificada) |
| Capa anticorrupción | `backend/app/integrations/util_bbdd/compare.py` | completado |
| Dominio, job y API | `backend/app/domain/runs/diff.py`, `backend/app/jobs/operations/compare.py`, `backend/app/api/v1/{runs,schemas_diff}.py` | completado |
| Tests | `backend/tests/{unit/test_compare_units.py,api/test_compare.py,integration/test_bench_compare.py}` | completado |
| Frontend | `frontend/src/features/runs/compare/` | completado |
| E2E | `frontend/e2e/compare.spec.ts`, `frontend/e2e/fixtures/tienda_v2.sql` | ejecutado |
| Docs | `docs/guides/comparacion.md`, GAPS G23–G25, CHANGELOG, ROADMAP | completado |

## Directrices para Futuras IAs
- **[util_bbdd-compare-labels]**: `SchemaComparator` pone en `source_label`/`target_label` la URL de conexión sin contraseña (host, usuario, ruta del SQLite). Hay que pasar siempre el diff por `relabel` antes de serializarlo o de llamar a un reporter, y dar `filename` explícito a `render` (G23).
- **[schema-inspector]**: con un `Inspector` de SQLAlchemy, el schema de Oracle va normalizado (`bench`). Se resuelve con `resolve_schema` contra `get_schema_names()`; si no, un nombre mal escrito produce un diff vacío sin error.
- **[informes-html-util_bbdd]**: antes de servir un HTML de util_bbdd en el sitio aislado (ADR-007), hay que buscar `<script src="https://…">`. La CSP los bloquea, y si el script en línea depende de ellos, aborta entero. Para el informe de comparación existe `localize_mermaid` (G25).
- **[diff-json]**: el diff se guarda en `outputs/diff/schema_diff.json` (`format: 1`). Si util_bbdd añade campos, los modelos de `schemas_diff.py` los ignoran (`extra="ignore"`). Si cambia la forma, hay que subir `DIFF_FORMAT` y adaptar `leaf_items`.
- **[evolucion]**: la clave de una diferencia es (tipo, tabla, nombre, atributo) en minúsculas. Las FK sin nombre que genera el motor pueden cambiar de nombre entre fechas y aparecer como nueva + resuelta.
- **[script-sql]**: el SQL de `SqlDiffReporter` incluye `DROP`. No se ejecuta en esta fase. La Fase 7 (migración DDL) debe exigir rol autorizado, conexión no `read_only`, modo seco y confirmación antes de aplicar nada.
- **[e2e-texto]**: `getByText('Correcta')` sin `exact: true` también encuentra «comparaciones correctas». Para los estados hay que usar texto exacto.
- **[shell-rm]**: en los scripts de E2E, `rm -f "$S/$db"` lo bloquea la comprobación de seguridad. Hay que usar `"${S:?}/${db:?}"`.

## Veredicto final
Veredicto: CLOSED (Fase 6 cumplida, mejora opcional incluida; DoD verificada contra SQLite real, 5 motores bench y E2E)
Pendientes al cierre:
- Riesgos residuales:
  - Diffs muy grandes: el visor no los sirve por encima de 20 MB (los informes sí).
  - Los diagramas Mermaid del informe HTML se ven como texto (G25).
- El CI no ejecuta Playwright ni la integración.
- Sin commit (pendiente de petición). Siguiente paso: `/phase 7` (migración DDL).
