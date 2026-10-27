# TRACEABILITY

## Session metadata
- id: 2026-10-27-gaps-ola4
- fecha: 2026-10-27
- rama: develop
- skill: new_feature + version_closure
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION de W-4 del plan de huecos (util_bbdd 4.4.0) → 1.4.0

## Prompt issued
W-4.0 y fases W-V1 … W-V5 de `docs/plan/UTIL_BBDD_GAPS_PLAN.md` con util_bbdd 4.4.0, un commit por fase en `develop`.
Restricciones: el volcado sigue exigiendo `can_write_data` + owner, conexión no `read_only`, vista previa y
confirmación (ADR-009); cancelar el volcado solo entre lotes y con constraints restauradas; `restore_constraints` con el
mismo control que el volcado y auditoría (S2); `redact_values` se mantiene (W-V5); registro en §6 del plan y GAPS
G6/G29/G31/G32/G33/G34 por fase. Después, «añadir `service.py` y lanzar el cierre»: bench, compose, E2E y versión.

## Context supplied
- Plan canónico y su registro (§6); `UTIL_BBDD_GAPS.md` (G1, G6, G29, G31-G34); ADR-002, ADR-009 y ADR-010.
- Release `v4.4.0` de util_bbdd: tag remoto y assets comprobados; firmas leídas en el repo origen (solo lectura) en
  el tag; wheel con SHA-256 `2c46c8ad…25e2`, igual al de `uv.lock`. La sesión de util_bbdd no registró la ola 4 en §6:
  se reconstruyó desde sus commits y su `CHANGELOG.md`.

## AI output summary
- AUDIT_PLAN `GO_CONDICIONAL`; decisiones aceptadas por el usuario: D1 `dump_apply` en `CANCEL_BETWEEN_STEPS_ONLY`;
  D2 `dump_restore` como job; D3 restauración automática del worker; D4 bloquear `dump_apply` y la purga con diario
  pendiente; D5 quitar `warnings` y `date_columns` de la vista previa.
- W-4.0 `c7c0db9`: pin 4.4.0 (lock con uv 0.12.22); test de G33 a `xfail(strict=True)` (F3).
- W-V1 `48150f1`: `build_preview` sobre `DumpOrchestrator.plan()` con `_config` común; réplica del orden retirada.
- W-V2 `e1ea62a`: `DumpProgress`, volcado cancelable entre lotes, `cancelled`/`completed_tables` (OpenAPI + `gen:api`).
- W-V3 `f1cbffd`: diario en `work/`, `dump_restore` (manual y automática), bloqueos, `GET /runs/{id}/dump-constraints`.
- W-V4 `4e26982`: fuera los avisos de G32 y G33 (OpenAPI + `gen:api`).
- W-V5 `6718ebb`: `_clean` sin `_engine_message`; `redact_values` con el patrón de PostgreSQL.
- `b0f3a56`: cambio del IDE en `purge_run` (sin `list()`) que el usuario pidió añadir; comprobado que es seguro.
- VERSION: 1.4.0 (commit `release: v1.4.0`).

## Evidencias
- Backend: ruff, mypy, pytest 673 passed / 91 skipped; `export_openapi.py --check`.
- Frontend: format, lint, typecheck, Vitest 126 passed, build.
- Docs: `zensical build --strict`.
- Bench (`pytest -m integration`, SQL Server con `UTIL_BBDD_BENCH_MSSQL_PORT=51833`): 83 passed, 6 skipped. Incluye la
  restauración real de constraints en PostgreSQL, SQL Server y Oracle y «apartar» en Oracle (G32).
- `docker compose up -d --build` + `/api/health` 200 (1.4.0, `util_bbdd_version` 4.4.0, worker ok).
- E2E: 23 specs en verde con `--workers=1` (21 en la pasada completa; connections y migrate repetidos con
  `UTIL_BBDD_BENCH_PASSWORD`, que esa sesión de PowerShell no tenía).

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Registro de la ola | `docs/plan/UTIL_BBDD_GAPS_PLAN.md` §6 («Ola 4» y «W-4») | completado |
| Enmiendas | `docs/adr/ADR-009-volcado-de-datos.md`, `ADR-002-ejecucion-de-jobs.md`, `ADR-010-carga-bulk.md` | completado |
| Componente nuevo | `frontend/src/features/runs/dump/PendingConstraints.tsx` | completado |
| Logs de validación | `build/logs/w40_*`, `wv1_*` … `wv5_*`, `ola4_*` | local (no versionado) |

## Directrices para Futuras IAs
- **[volcado]**: `dump_apply` está en `CANCEL_BETWEEN_STEPS_ONLY` del worker (como `migrate_apply`): cancelar nunca
  termina el subproceso, solo el `job_timeout`. Al cancelar, util_bbdd lanza `OperationCancelledError` sin `DumpResult`:
  `result.json` lo escribe `cancelled_result` con las tablas que `DumpProgress.completed` vio terminar.
- **[volcado]**: el diario de constraints vive en `work/constraints_journal.json` del run (`DUMP_JOURNAL_PATH`) junto a
  `work/target.json` (alias e id de la conexión destino, que escribe el job antes de `run_dump`). `run_dump` solo borra
  `work/` si no queda diario. Mientras exista, `dump_journal()` lo detecta y bloquea el volcado en ese destino y la
  purga (manual, retención y cuota).
- **[volcado]**: SQLite y MySQL/MariaDB no llevan diario (`_JOURNAL_ENGINES`: `mssql`, `oracle`, `postgresql`); los
  tests de API de `dump_restore` añaden `sqlite` con `monkeypatch.setitem`, que solo vale en el proceso de los tests
  (el job del worker corre en otro proceso).
- **[volcado]**: `build_preview` y `run_dump` construyen el `DumpConfig` con `_config`; con `on_error="isolate"`
  `DumpConfig` exige `rejects_csv_path` aunque `plan()` no lo escriba.
- **[volcado]**: la posición de cada tabla en la vista previa es su índice en `load_order` (util_bbdd da `-1` a las
  tablas sin destino); no cambiarla sin aceptar que cambia `structure_hash`.
- **[seguridad]**: `_clean`/`redact_values` siguen siendo necesarios aunque util_bbdd 4.4.0 sanee `error_msg`: el
  `error_msg` de los contadores PK viene de `bulk` y no está saneado.
- **[e2e]**: exporta `UTIL_BBDD_BENCH_PASSWORD` (variable de usuario de Windows) en la misma sesión que lanza
  Playwright, o se saltan connections y migrate. El admin `e2e_ola3b` sigue sirviendo para el E2E.
- **[proceso]**: la sesión de util_bbdd puede no registrar su ola en §6 del plan de la web; reconstrúyela desde sus
  commits y su `CHANGELOG.md` en W-x.0.

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Push de `develop`, merge a `main` y tag `v1.4.0` (propietario).
- Usuarios admin locales `e2e_ola3` y `e2e_ola3b` en la instancia de `docker compose`: desactivarlos si no se van a
  reutilizar.
