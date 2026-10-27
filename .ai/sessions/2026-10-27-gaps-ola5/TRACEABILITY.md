# TRACEABILITY

## Session metadata
- id: 2026-10-27-gaps-ola5
- fecha: 2026-10-27
- rama: develop
- skill: new_feature + version_closure
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION de W-5 del plan de huecos (util_bbdd 4.5.0) → 1.5.0

## Prompt issued
W-5.0 y fases W-B1 … W-B3 de `docs/plan/UTIL_BBDD_GAPS_PLAN.md` con util_bbdd 4.5.0, un commit por fase en `develop`.
Restricciones: la carga sigue exigiendo `can_write_data` + owner, conexión no `read_only`, vista previa, `confirm_rows`
y confirmación (ADR-010); el recuento antes/después del destino se mantiene como verificación (W-B1);
`accept_non_atomic` solo si `plan.atomic` es `False` (W-B2); cancelar la carga solo entre lotes; `generar_sql`/`dry_run`
siempre explícitos (G35); registro en §6 del plan y GAPS G1/G35/G36/G37 por fase. Después, «sí» al cierre.

## Context supplied
- Plan canónico y su registro (§6); `UTIL_BBDD_GAPS.md` (G1, G35, G36, G37); ADR-002 y ADR-010.
- Release `v4.5.0` de util_bbdd: tag remoto y assets comprobados; firmas leídas en el repo origen (solo lectura) en el
  tag; wheel con SHA-256 `64a90d10…0ce5`, igual al de `uv.lock`. La ola 5 se reconstruyó en §6 desde su CHANGELOG.

## AI output summary
- AUDIT_PLAN `GO_CONDICIONAL`; decisiones aceptadas: D1 regla de verificación (`verify`); D2 `require_atomic=True` sin
  `accept_non_atomic`; D3 `bulk_apply` en `CANCEL_BETWEEN_STEPS_ONLY`; D4 `dry_run` en lugar de `generar_sql`.
- W-5.0 `2506adf`: pin 4.5.0 (lock con uv 0.12.22, sin la retirada ajena de una rueda de zensical); suite en verde con
  `-W error::FutureWarning`.
- W-B1 `a326ac5`: `committed` y `verified` en el resultado (OpenAPI + `gen:api`); `dry_run` explícito.
- W-B2 `6be0e3a`: `parallel.atomic`, `plan_atomic` (backend y UI) y `require_atomic` (OpenAPI + `gen:api`).
- W-B3 `eed7da9`: `RunProgress` (fase `rows`), carga cancelable entre lotes, `cancelled` (OpenAPI + `gen:api`);
  `NOT_CANCELLABLE_RUNNING` retirado en backend y UI.
- VERSION: 1.5.0 (commit `release: v1.5.0`).

## Evidencias
- Backend: ruff, mypy, pytest 692 passed / 91 skipped; `export_openapi.py --check`.
- Frontend: format, lint, typecheck, Vitest 130 passed, build.
- Docs: `zensical build --strict`.
- Bench (`pytest -m integration`, SQL Server con `UTIL_BBDD_BENCH_MSSQL_PORT=51833`): 83 passed, 6 skipped. Incluye
  los contadores de G37 (`committed`, `verified`) en los 5 motores.
- Cancelación real con util_bbdd sobre SQLite: carga atómica cancelada tras el primer lote, sin filas en el destino.
- `docker compose up -d --build` + `/api/health` 200 (1.5.0, `util_bbdd_version` 4.5.0, worker ok).
- E2E: 23 specs en verde a la primera con `--workers=1` y `UTIL_BBDD_BENCH_PASSWORD` en la misma sesión.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Registro de la ola | `docs/plan/UTIL_BBDD_GAPS_PLAN.md` §6 («Ola 5» y «W-5») | completado |
| Enmiendas | `docs/adr/ADR-010-carga-bulk.md`, `docs/adr/ADR-002-ejecucion-de-jobs.md` | completado |
| Logs de validación | `build/logs/w50_*`, `wb1_*` … `wb3_*`, `ola5_*` | local (no versionado) |

## Directrices para Futuras IAs
- **[carga]**: `committed` (`last_operation_rows_committed`) cuenta filas **enviadas** y confirmadas, incluidas las
  apartadas y las claves inexistentes de un update/delete; no es «filas modificadas». La comprobación es `verify`
  (insert crece en `committed`, delete decrece en `matches`, update no cambia) y solo se aplica sin rechazos, error,
  cancelación ni particiones fallidas (`verified=null` si no).
- **[carga]**: sin `accept_non_atomic` la carga se lanza con `ParallelOptions(require_atomic=True)`; `plan_atomic` (y su
  gemela en `BulkPreviewViewer.tsx`) usa `workers <= 1` para las vistas previas anteriores a la 1.5.0.
- **[jobs]**: `CANCEL_BETWEEN_STEPS_ONLY` = `migrate_apply`, `dump_apply`, `bulk_apply`; `NOT_CANCELLABLE_RUNNING` ya
  no existe. Cancelar una carga sin plan paralelo la deshace **entera**: los textos de la UI lo dicen antes de confirmar.
- **[dependencias]**: al relockear con `--upgrade-package util_bbdd` uv puede arrastrar cambios ajenos del índice
  (p. ej. ruedas retiradas de zensical); revisar el diff de `uv.lock` y dejar solo util_bbdd, comprobando después con
  `uvx --from uv==0.12.22 uv lock --check`.
- **[tests]**: `pytest -W error::FutureWarning` comprueba que la web pasa `generar_sql`/`dry_run` y `truncate_target`
  explícitos (avisos de util_bbdd 4.4.0 y 4.5.0).
- **[proceso]**: tampoco en esta ola la sesión de util_bbdd registró su tabla en §6; se reconstruye en W-x.0.

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Push de `develop`, merge a `main` y tag `v1.5.0` (propietario).
- Cancelación de una carga **paralela** sin probar contra el bench (con los datos de prueba el plan es de un hilo).
