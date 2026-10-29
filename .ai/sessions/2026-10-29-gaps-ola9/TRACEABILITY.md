# TRACEABILITY

## Session metadata
- id: 2026-10-29-gaps-ola9
- fecha: 2026-10-29
- rama: develop
- skill: new_feature + refactor + version_closure
- fase: PLAN + AUDIT_PLAN de la ola 9 del plan de huecos (G44); IMPLEMENT + AUDIT_CODE + VERSION de W-9 (util_bbdd
  5.1.0) → 1.7.1

## Prompt issued
1. PLAN y AUDIT_PLAN de G44 (precisión de `NUMBER` de Oracle en `execute_custom_*`) para una ola futura de util_bbdd;
   aprobado con las recomendaciones (D9-1 … D9-4).
2. Tras la release de util_bbdd 5.1.0 (otra sesión): `/new-feature` W-9.0, `/refactor` W-9.1 («Adelante» en cada
   una) y el cierre `release: v1.7.1`.

## Context supplied
- Plan canónico y su registro (§6); `UTIL_BBDD_GAPS.md`; `docs/guides/publicar_version.md`.
- util_bbdd 5.0.0 leída en el repo origen (solo lectura) para planificar; 5.1.0 en el wheel instalado
  (`executors/_oracle_numbers.py`). Release `v5.1.0`: tag remoto y wheel comprobados; SHA-256 `52783997…1d1b86`, igual
  al de `uv.lock`.
- Registro de la ola 9 de util_bbdd en §6 del plan (`a9b86e0`, de la sesión de util_bbdd).

## AI output summary
- Plan de la ola 9 `f2db8e0` (GO_CONDICIONAL; D9-1 … D9-4). El conversor se probó en el bench con util_bbdd 5.0.0
  antes de proponerlo.
- W-9.0 `1bd3801`: pin 5.1.0 sin cambios de código; el rodeo y el conversor conviven sin cambiar el resultado (R9-6).
- W-9.1 `fa13622`: fuera `_prepare_driver` y `_oracle_number`; `_run_read_only` sin `db_type`; `FLOAT` vuelve a ser
  número.
- VERSION: 1.7.1 (PATCH, D9-3; commit `release: v1.7.1`).

## Evidencias
- Backend: ruff, mypy, pytest con `-W error::FutureWarning -W error::DeprecationWarning`; `export_openapi.py --check`.
- Frontend: format, lint, typecheck, Vitest, build; `gen:api` sin cambios en `schema.d.ts`.
- Docs: `zensical build --strict`.
- Bench: comparación de tipos sin el rodeo (Oracle 23ai) antes de W-9.1; bench completo en el cierre (89 passed,
  10 skipped por diseño).
- Backend 700 passed / 101 skipped; frontend 131 tests.
- `docker compose up -d --build` + `/api/health` 200 (1.7.1, util_bbdd 5.1.0, worker ok), copia previa
  `ubw-backup-20261029T210408Z`.
- E2E: primera pasada 22 de 23 (`migrate.spec.ts` agotó sus 300 s tras aplicar, con el fichero en 5 min frente a 15 s
  solo); el spec solo pasa y una segunda pasada completa da 23 passed en 1,9 min. Tiempos del worker, no de la versión.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Plan y registro de la ola 9 | `docs/plan/UTIL_BBDD_GAPS_PLAN.md` (Grupo 9, §4 «Ola 9», §6 «W-9») | completado |
| Huecos | `docs/plan/UTIL_BBDD_GAPS.md`: G44 resuelto | completado |
| Logs de validación | `build/logs/w9.0_*`, `w9.1_*`, `v1.7.1_*` | local (no versionado) |

## Directrices para Futuras IAs
- **[sql]**: la precisión de `NUMBER` en Oracle la da util_bbdd (`prepare_query_cursor` pone el conversor en el cursor
  y **respeta** el `outputtypehandler` de la conexión). La web no debe tocar `oracledb.defaults` ni poner un conversor
  propio; el test `test_free_sql_task_leaves_the_oracledb_defaults_alone` lo vigila.
- **[sql]**: el test del bench `test_free_select_oracle_numbers_keep_precision` (`NUMBER(38,3)` y `FLOAT`) es la alarma
  si util_bbdd deja de convertir.
- **[dependencias]**: cada `uv lock` con uv 0.12.22 sigue queriendo retirar la rueda `armv7l` de zensical 0.0.67; se ha
  descartado otra vez en W-9.0 y en el cierre.

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Ninguno de la ola 9. Sigue pendiente el `chore(deps)` de la rueda `armv7l` de zensical.
- `migrate.spec.ts` puede agotar sus 300 s si el worker va cargado (ver Evidencias): vigilar en la próxima release.
