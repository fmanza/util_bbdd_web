# TRACEABILITY

## Session metadata
- id: 2026-10-26-gaps-ola3
- fecha: 2026-10-26
- rama: develop
- skill: new_feature + version_closure
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION de W-3 del plan de huecos (util_bbdd 4.3.0) → 1.3.0

## Prompt issued
W-3.0 y fases W-M1 … W-M4 de `docs/plan/UTIL_BBDD_GAPS_PLAN.md` con util_bbdd 4.3.0, un commit por fase en `develop`.
Restricciones: modo seco obligatorio y doble confirmación de `migrate_apply` sin cambios (ADR-008); los `plan.json`
antiguos se replanifican; cancelación de la aplicación solo entre sentencias; registro en §6 del plan y GAPS
G4/G26/G27/G28 por fase. Después, «ejecuta lo que falta»: bench, E2E y cierre de versión.

## Context supplied
- Plan canónico y su registro (§6); `UTIL_BBDD_GAPS.md` (G1, G4, G26, G27, G28); ADR-002, ADR-006 y ADR-008.
- Release `v4.3.0` de util_bbdd: firmas leídas en el repo origen (solo lectura) en el tag; wheel con SHA-256
  `3af894d5…70be`, igual al de `uv.lock`.

## AI output summary
- AUDIT_PLAN `GO_CONDICIONAL`; decisiones aceptadas por el usuario: `migration_plan.json` aparte, el worker nunca mata
  `migrate_apply` al cancelar, confirmación de la cancelación solo en la UI, conflictos también de vistas.
- W-3.0 `ac04574`: pin 4.3.0 (lock con uv 0.12.22); solo los tests de versión.
- W-M1 `de05b61`: `catalog.migration_engines()` desde `MigrationPlanner.supported_sources/targets()`; test de contrato
  con el `Literal` `MigrationEngine`.
- W-M2 `38fd027`: FK alineadas por util_bbdd; `fk_mismatches`/`fk_blocking` se mantienen como defensa; manager falso de
  catálogo para tests (`tests/unit/_migration_source.py`).
- W-M3 `69e3eaa`: `migration_plan.json` (`to_dict()`); `restore_plan` (`from_dict()` + hash del `plan.json` revisado) y
  `replan` solo para planes anteriores a la 1.3.0; `check_target`; fallo desde `MigrationStatementError`.
- W-M4 `de8bc33`: progreso por sentencia, cancelación entre sentencias (`CANCEL_BETWEEN_STEPS_ONLY`), campo
  `cancelled` del informe (OpenAPI + `gen:api`).
- `5e9fc9c`: los E2E buscan al usuario antes de «Editar» (paginación de 50).
- VERSION: 1.3.0 (commit `release: v1.3.0`).

## Evidencias
- Backend: ruff, mypy, pytest 656 passed / 88 skipped; `export_openapi.py --check`.
- Frontend: format, lint, typecheck, Vitest 122 passed, build.
- Docs: `zensical build --strict`.
- Bench (`pytest -m integration`): 65 passed + 15 de SQL Server repetidos con `UTIL_BBDD_BENCH_MSSQL_PORT=51833`
  (80 passed, 5 skipped). Incluye Oracle → MariaDB aplicado de verdad (G28).
- `docker compose up -d --build` + `/api/health` 200 (`util_bbdd_version` 4.3.0).
- E2E: 23 specs en verde (18 a la primera; bulk, dump, explorer, migrate y storage tras `5e9fc9c`; bulk repetido solo
  por una carrera de permisos con dump en `--workers=2`).

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Registro de la ola | `docs/plan/UTIL_BBDD_GAPS_PLAN.md` §6 | completado |
| Enmiendas | `docs/adr/ADR-008-aplicar-migraciones.md`, `docs/adr/ADR-002-ejecucion-de-jobs.md` | completado |
| Logs de validación | `build/logs/w30_*`, `wm1_*` … `wm4_*`, `ola3_*` | local (no versionado) |

## Directrices para Futuras IAs
- **[migración]**: un plan tiene dos ficheros: `outputs/plan/plan.json` (visor, formato propio con `statements_hash`) y,
  desde la 1.3.0, `outputs/plan/migration_plan.json` (`MigrationPlan.to_dict()`). Sin el segundo, el plan es anterior a
  la 1.3.0 y `migrate_apply` lo replanifica (`replan`); no quitar ese camino mientras queden planes de la 1.2.0.
- **[migración]**: `restore_plan` compara `statements_sha256()` del plan reconstruido con el `statements_hash` de
  `plan.json` (el revisado), no solo con el que viaja en `migration_plan.json`; los dos usan el mismo algoritmo
  (sentencias unidas con NUL).
- **[migración]**: `check_target` cuenta como conflicto también las vistas del plan que ya existen; `report.statements`
  sale de `execute(None, dry_run=True).total` (sin las sentencias de solo comentarios).
- **[jobs]**: `migrate_apply` está en `CANCEL_BETWEEN_STEPS_ONLY` del worker: cancelar nunca termina el subproceso
  (solo el `job_timeout`). No moverla a `COOPERATIVE_OPERATIONS`, que mata a los 60 s.
- **[tests]**: `tests/unit/_migration_source.py` planifica y comprueba destinos sin BD (fuente de catálogo en memoria);
  con un `MagicMock` como manager, el `execute()` real de util_bbdd corre sobre `raw_connection().cursor()`.
- **[bench]**: el SQL Server del bench de esta máquina escucha en `51833`: exporta `UTIL_BBDD_BENCH_MSSQL_PORT=51833`.
  La contraseña está en la variable de usuario de Windows `UTIL_BBDD_BENCH_PASSWORD` (no en el proceso de Git Bash).
- **[e2e]**: la lista de usuarios pagina de 50 por nombre; los specs deben buscar el usuario antes de «Editar». Bulk y
  dump cambian los permisos del mismo admin: con `--workers=2` pueden pisarse; repetir el que falle con `--workers=1`.

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Push de `develop`, merge a `main` y tag `v1.3.0` (propietario).
- Usuarios admin locales `e2e_ola3` y `e2e_ola3b` creados para el E2E en la instancia de `docker compose`: desactivarlos
  si no se van a reutilizar.
