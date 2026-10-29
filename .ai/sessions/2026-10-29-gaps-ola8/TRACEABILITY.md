# TRACEABILITY

## Session metadata
- id: 2026-10-29-gaps-ola8
- fecha: 2026-10-29
- rama: develop
- skill: new_feature + version_closure
- fase: PLAN + AUDIT_PLAN de la ola 8 del plan de huecos; IMPLEMENT + AUDIT_CODE + VERSION de W-8 (util_bbdd 5.0.0) →
  1.7.0

## Prompt issued
1. `/new-feature`: planificar la ola 8 en `docs/plan/UTIL_BBDD_GAPS_PLAN.md` (D4): util_bbdd 5.0.0 con valores por
   defecto seguros (G30, G35, G2) más G42 y G43; fases U-8.x y W-8.x; solo documentación, un commit `docs(plan)`.
   Decisiones aprobadas, con D8-8 cambiada a «incluir como U-8.6».
2. Tras la release de util_bbdd 5.0.0 (otra sesión): W-8.0 … W-8.4, una por petición («si», «IMPLEMENT»,
   «Adelante», «Implement»), y el cierre `release: v1.7.0`.

## Context supplied
- Plan canónico y su registro (§6); `UTIL_BBDD_GAPS.md`; `docs/guides/publicar_version.md`.
- Firmas de util_bbdd 4.6.0 leídas en el repo origen (solo lectura) para planificar; las de 5.0.0, en el wheel
  instalado. Release `v5.0.0`: tag remoto y wheel comprobados; SHA-256 `f25a81c3…14ee2d0`, igual al de `uv.lock`.
- Registro de la ola 8 de util_bbdd en §6 del plan (`c90781f`, de la sesión de util_bbdd).

## AI output summary
- Plan de la ola 8 `940081d` (GO_CONDICIONAL; D8-1 … D8-8). U-8.6 (retirada de `columnas_auditoria` y
  `encoding_errors`) añadió W-8.1 en la web.
- W-8.0 `e6d6f1e`: pin 5.0.0 sin cambios de código.
- W-8.1 `7327e42`: migración `0011` (fuera `encoding_errors` de las conexiones MariaDB). Corrige F8-5: la UI sí editaba
  esas conexiones; fallaban los clientes de la API y la ficha.
- W-8.2 `314f42e`: consola sobre `execute_custom_result`. El bench destapó G44 (oracledb da `NUMBER` como `float`):
  rodeo con `fetch_decimals` en el subproceso. El riesgo de los LOB no se confirmó.
- W-8.3 `dbeb07e`: versión del servidor desde `get_server_version_info()`; idéntica en los 5 motores del bench.
- W-8.4 `55bcf2b`: docstrings y GAPS G2, G30, G35.
- VERSION: 1.7.0 (commit `release: v1.7.0`).

## Evidencias
- Backend: ruff, mypy, pytest con `-W error::FutureWarning -W error::DeprecationWarning` 706 passed / 101 skipped;
  `export_openapi.py --check`.
- Frontend: format, lint, typecheck, Vitest 131 passed, build; `gen:api` sin cambios en `schema.d.ts`.
- Docs: `zensical build --strict`.
- Comparaciones contra el bench: celdas de la consola antes/después (iguales salvo Oracle: mayúsculas y `NUMBER`);
  versión del servidor antes/después (idéntica en Oracle, PostgreSQL, MySQL, MariaDB y SQL Server).
- Bench (`pytest -m integration -W error::FutureWarning`, SQL Server con `UTIL_BBDD_BENCH_MSSQL_PORT=51833`): 89
  passed, 10 skipped (por diseño: solo Oracle, o solo motores que ponen la clave en el mensaje).
- `docker compose up -d --build` + `/api/health` 200 (1.7.0, `util_bbdd_version` 5.0.0, worker ok); `config.db` de la
  aplicación en la revisión `0011`.
- E2E: 23 specs en verde con `--workers=1`, `UBW_E2E_SQLITE=1` y `UBW_E2E_MIGRATE=1` (fixture de migración
  preparada y limpiada en el bench), con los límites de peticiones altos de la guía; después, compose con sus límites.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Plan y registro de la ola 8 | `docs/plan/UTIL_BBDD_GAPS_PLAN.md` (Grupo 8, §4 «Ola 8», §6 «W-8») | completado |
| Huecos | `docs/plan/UTIL_BBDD_GAPS.md`: G2, G30, G35, G42, G43 resueltos; G44 nuevo | G44 abierto |
| Migración | `backend/alembic/versions/0011_drop_encoding_errors.py` | completado |
| Logs de validación | `build/logs/ola8_*`, `w8.0_*` … `w8.4_*`, `v1.7.0_*` | local (no versionado) |

## Directrices para Futuras IAs
- **[sql]**: la consola usa `execute_custom_result`, que va por la conexión del driver y no por SQLAlchemy. Los tipos
  de las celdas son los del driver: comparar contra el bench antes de cambiar de método o de driver.
- **[sql]**: en Oracle, `oracledb.defaults.fetch_decimals = True` en `_prepare_driver` es el rodeo de G44. Es global,
  pero cada tarea corre en un subproceso *spawn* propio. No llamarlo desde código que corra en el proceso de la API ni
  de los tests.
- **[conexiones]**: la versión del servidor sale de `get_server_version_info()` y, si no da números, del texto de
  `get_server_version()`; `_sqlalchemy_version` ya no existe.
- **[conexiones]**: el formulario solo envía los parámetros que el motor declara, así que un parámetro retirado por
  util_bbdd desaparece al guardar desde la UI. Los clientes de la API y la ficha sí lo arrastran: cuando util_bbdd
  retire un parámetro, una migración de datos como la `0011` lo quita de las conexiones guardadas.
- **[bench]**: `UTIL_BBDD_BENCH_PASSWORD` es una variable de usuario de Windows; un VS Code arrancado antes no la
  hereda. Se lee con `[Environment]::GetEnvironmentVariable('UTIL_BBDD_BENCH_PASSWORD','User')`. SQL Server está en
  el puerto 51833.
- **[dependencias]**: cada `uv lock` con uv 0.12.22 sigue queriendo retirar la rueda `armv7l` de zensical 0.0.67; se ha
  vuelto a descartar en W-8.0 y en este cierre. Pendiente un `chore(deps)` propio. **Resuelto** en `a281292` (`chore(deps)`): PyPI ya no lista esa rueda y se retiró del lock.

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Push de `develop`, merge a `main`, tag `v1.7.0` y GitHub Release (propietario).
- G44 para una ola futura de util_bbdd. HSQLDB sin bench en la web (versión del servidor cubierta por el unitario).
- Las credenciales del admin E2E son ahora variables de usuario de Windows (`UBW_E2E_ADMIN_USER`/`_PASSWORD`).
