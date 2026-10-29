# TRACEABILITY

## Session metadata
- id: 2026-10-29-gaps-ola6
- fecha: 2026-10-29
- rama: develop
- skill: new_feature + version_closure
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION de W-6 del plan de huecos (util_bbdd 4.6.0) → 1.6.0

## Prompt issued
W-6.0 y fases W-T1 … W-T4 de `docs/plan/UTIL_BBDD_GAPS_PLAN.md` con util_bbdd 4.6.0, un commit por fase en `develop`.
Restricciones: secretos nunca en claro (ADR-004); `KNOWN_PARAMS` y su test se mantienen como alarma (W-T2); en el SQL
libre el guardián `sqlglot`, la transacción propia y la validación de parámetros se mantienen como defensa (W-T4); la
ficha de motores no cambia lo que muestra salvo que util_bbdd aporte más; registro en §6 del plan y GAPS G5/G8/G10-G15/
G17-G20 por fase. Después, «sí» al cierre.

## Context supplied
- Plan canónico y su registro (§6); `UTIL_BBDD_GAPS.md`; `docs/guides/publicar_version.md` (nueva, `abcb828`).
- Release `v4.6.0` de util_bbdd: tag remoto y assets comprobados; firmas leídas en el repo origen (solo lectura) en el
  tag; wheel con SHA-256 `f22e18f3…4a57`, igual al de `uv.lock`. Su CHANGELOG ya dice qué necesita cada fase `W-`.

## AI output summary
- AUDIT_PLAN `GO_CONDICIONAL`; el usuario respondió «IMPLEMENT» (D1-D4 tomadas como propuestas). D1: matriz completa
  en la ficha y tabla de motores sin cambios; D2: clase `port` expuesta y un parámetro sin clase → `blocked`;
  **D3 cambiada al implementar**: la versión sigue saliendo de SQLAlchemy (`get_server_version()` da `23.0.0.0.0` en
  Oracle 23ai, G43); D4: la consola mantiene su ejecución (G42).
- W-6.0 `9cb8827`: pin 4.6.0 según la guía; G11 resuelto sin fase.
- W-T1 `b33e6ad`: capacidades, drivers y `default_driver` desde util_bbdd; ficha comparada antes/después.
- W-T2 `9b3f8d8`: `param_kind` desde `connection_params.kinds`; `build_params` sin mezcla.
- W-T3 `6dbd129`: `ping()`, `get_schema_names()`, `current_schema()`; comparado contra el bench.
- W-T4 `fe0e49c`: test de contrato de `execute_custom_many`; G42.
- VERSION: 1.6.0 (commit `release: v1.6.0`), con la guía de publicación y Dependabot que ya estaban en `[Unreleased]`.

## Evidencias
- Backend: ruff, mypy, pytest 697 passed / 91 skipped; `export_openapi.py --check`.
- Frontend: format, lint, typecheck, Vitest 131 passed, build.
- Docs: `zensical build --strict`.
- Comparaciones: ficha de los 7 motores (solo se añaden capacidades; `port` es la única clase nueva); `build_params` con
  y sin mezcla (misma salida); versión, schemas, por defecto y clasificación de fallos contra el bench (6 motores).
- Bench (`pytest -m integration`, SQL Server con `UTIL_BBDD_BENCH_MSSQL_PORT=51833`): 83 passed, 6 skipped.
- `docker compose up -d --build` + `/api/health` 200 (1.6.0, `util_bbdd_version` 4.6.0, worker ok).
- E2E: 23 specs en verde con `--workers=1`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Registro de la ola | `docs/plan/UTIL_BBDD_GAPS_PLAN.md` §6 («Ola 6» y «W-6») | completado |
| Huecos nuevos | `docs/plan/UTIL_BBDD_GAPS.md` G42 (columnas en `execute_custom_*`), G43 (versión Oracle) | abiertos |
| Logs de validación | `build/logs/w60_*`, `wt1_*` … `wt4_*`, `ola6_*`, `r160_*` | local (no versionado) |

## Directrices para Futuras IAs
- **[catálogo]**: `EngineCapabilities` de la web es un espejo de `get_engine_capabilities`; el test
  `test_capabilities_mirror_util_bbdd` falla si util_bbdd renombra una capacidad (si no, se quedaría en `False`).
- **[conexiones]**: `param_kind` lee `ConnectionParamsManager.param_kinds`; clase ausente o desconocida → `blocked`.
  `KNOWN_PARAMS` sigue siendo la alarma de parámetros nuevos: revisar el parámetro antes de ampliarlo.
- **[conexiones]**: la versión del servidor de la prueba sale de `server_version_info` de SQLAlchemy y solo cae a
  `get_server_version()` sin SQLAlchemy (HSQLDB). No cambiarlo mientras G43 esté abierto.
- **[sql]**: la consola no usa `execute_custom_many` (G42: tuplas sin nombres de columna). Cuando falle
  `test_execute_custom_many_still_returns_rows_without_column_names`, util_bbdd ya da las columnas: revisar W-T4.
- **[dependencias]**: cada `uv lock` con uv 0.12.22 quiere retirar del lock la rueda `armv7l` de zensical 0.0.67 (ya
  no está en el índice). Se ha descartado en tres commits para no mezclarlo; conviene asumirlo una vez en un
  `chore(deps)` propio y dejar de revertirlo. **Resuelto** en `a281292` (`chore(deps)`): PyPI ya no lista esa rueda y se retiró del lock.
- **[proceso]**: `docs/guides/publicar_version.md` es el procedimiento de versión: incluye `UBW_TAG` en `.env.example`
  y `npm version X.Y.Z --no-git-tag-version`.

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Push de `develop`, merge a `main`, tag `v1.6.0` y GitHub Release (propietario).
- HSQLDB sin verificar (sin driver en esta máquina): prueba con `ping()` y schemas sin SQLAlchemy.
- G42 y G43 para una ola futura de util_bbdd; la ola 8 (5.0.0) sigue fuera de este plan (D4).
