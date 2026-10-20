# TRACEABILITY

## Session metadata
- id: 2026-10-20-fase2
- fecha: 2026-10-20
- rama: develop
- skill: phase
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION (Fase 2 del ROADMAP)

## Prompt issued
«Adelante» (tras la Fase 1). Respuestas a las preguntas de inputs: dependencias `react-hook-form + zod`; motores:
contenedores bench; alcance completo. Tras AUDIT_PLAN: «Si, UTIL_BBDD_BENCH_PASSWORD ya está, IMPLEMENT Fase 2»
(aprueba también `cryptography` como dependencia directa).

## Context supplied
- Ver `00_CONTEXT_SNAPSHOT.md`.

## AI output summary
- PLAN + AUDIT_PLAN: firmas verificadas en el wheel instalado; `GO_CONDICIONAL` (cryptography directa, *resolver*
  propio de Zod, contraseña de los bench, políticas por defecto). Resueltas con el usuario.
- Backend:
  - `integrations/util_bbdd/catalog.py`: fichas, matriz, clasificación de parámetros, drivers con `find_spec`,
    filtro de `cx_Oracle`, `driver_info` de SQL Server normalizado y `build_params` sobre `build_conn_params`.
  - `integrations/util_bbdd/probe.py`: prueba y readiness en subproceso *spawn* con timeout, saneado y
    `logging.disable` en el hijo.
  - `domain/engines`, `domain/connections/{errors,crypto,allowlist,params,service}`.
  - Modelos `Connection` y `AllowlistEntry`, migración `0003` (verificada con `alembic check` y
    upgrade/downgrade).
  - Routers `engines`, `connections` y `admin_allowlist`; `AppError` con `errors` por campo; producción exige
    `UBW_FERNET_KEYS`; CLI `rotate-secrets`.
  - Docker: `UBW_FILES_DIR=/data/files` y `mkdir` en el *entrypoint*.
- Revisión propia durante AUDIT_CODE: un host que no resuelve en DNS devolvía «no está en la allowlist» → ahora
  `connection_failed` (test nuevo y E2E ajustado a una IP de documentación).
- Tests backend: 78 nuevos (151 en total). Unitarios: cifrado y rotación, política de allowlist (13 casos), hosts de
  destino, validación de parámetros y *traversal*, catálogo frente a util_bbdd. API: CRUD, IDOR,
  compartidas, secretos ausentes de respuestas, BD, log y auditoría, prueba real con SQLite en subproceso, destino no
  permitido sin conexión, 429, allowlist y CLI. Integración: 11 contra los 5 bench de red.
- Contrato: `openapi.json` exportado y `schema.d.ts` regenerado (estable).
- Frontend:
  - Páginas: `features/engines` (matriz, ficha, `DriverBadges`), `features/connections` (lista, formulario dinámico
    generado con Zod desde la ficha, detalle con prueba, readiness y borrado) y `features/admin/AllowlistPage`.
  - Comunes: `components/zodResolver.ts`, `Problem.errors`, i18n y navegación.
  - Tests: 20 nuevos de Vitest (39) y `e2e/connections.spec.ts` (4 flujos, uno contra el bench PostgreSQL).
- Docs: guía `conexiones.md`, ADR-004 (notas), GAPS G4/G5/G8 actualizados y G10–G16 nuevos, arquitectura,
  despliegue, solución de problemas, incorporación, README.
- AUDIT_CODE:
  - Backend local: `uv sync`, `ruff format --check`, `ruff check`, `mypy --platform linux`, `pytest` (151 passed,
    11 skipped de integración) y `export_openapi --check` OK. En la imagen `backend-dev` (Linux, como el CI) también
    OK, con `mypy` sin opciones.
  - Integración (`-m integration` con la contraseña del bench cargada en el proceso): 11/11.
  - Frontend: `format:check`, `lint`, `typecheck`, `test` (39) y `build` OK; bundle principal de 479 kB.
  - `docker compose build` + `up`: *healthy*, migración 0002 → 0003 sobre el volumen existente, `/api/health` →
    0.3.0 `ok`, imagen de 768 MB (+1 MB).
  - Playwright contra el contenedor: 9/9, incluido contenedor → `host.docker.internal` → bench PostgreSQL con prueba
    y readiness reales.
  - Manual: `/engines` sin sesión → 401; POST sin CSRF → 403. La contraseña del bench aparece 0 veces en los logs del
    contenedor, en la salida E2E y en `config.db` + WAL.
  - Salidas en `build/logs/fase2_*.txt`.
- VERSION: 0.3.0 en backend, `uv.lock`, `package.json` y `package-lock.json`; CHANGELOG, ROADMAP (Fase 2 cerrada),
  `.ai/product.md`, sesión e `INDEX.md`.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | conversación de la sesión | emitido (GO_CONDICIONAL, condiciones resueltas) |
| Capa anticorrupción | `backend/app/integrations/util_bbdd/{catalog,probe}.py` | completado |
| Dominio | `backend/app/domain/{engines,connections}/` | completado |
| API + migración | `backend/app/api/v1/{engines,connections,admin_allowlist}.py`, `alembic/versions/0003_connections.py` | completado |
| Tests backend | `backend/tests/{unit,api,integration}/` | completado (151 + 11 de integración) |
| Frontend | `frontend/src/features/{engines,connections}/`, `features/admin/AllowlistPage.tsx`, `components/zodResolver.ts` | completado (39 tests) |
| E2E | `frontend/e2e/connections.spec.ts` | ejecutado (9/9 en total) |
| Docs | `docs/guides/conexiones.md`, ADR-004, GAPS, guías, CHANGELOG, ROADMAP | completado |

## Directrices para Futuras IAs
- **[bash-windows]**: en este equipo, un heredoc de Git Bash con `«»` u otros caracteres no ASCII falla con «unexpected EOF while looking for matching `''»; escribir el fichero (o el script Python) con la herramienta Write y ejecutarlo después.
- **[npm-before]**: `npm install --before=<fecha>` falla con `notarget` porque Dependabot ya subió dependencias posteriores al corte; para paquetes nuevos, comprobar la fecha con `npm view <pkg> time --json` (`npm view <pkg> version --before=…` **no** filtra) e instalar la versión exacta con `--save-exact`.
- **[util_bbdd-catalogo]**: `get_db_type_info_static(db_type)["driver_info"]` es un `dict` salvo en SQL Server (lista); `connection_params.required` es una lista de nombres sin tipo; `EngineReadinessAdvisor` se importa de `util_bbdd.connection`, no de `connection._advisory` (G14).
- **[util_bbdd-build]**: `build_conn_params` descarta opcionales como `sslmode`; para conectar, usar `catalog.build_params` (`{**build_conn_params(...), **params}`) (G15).
- **[util_bbdd-secretos]**: `SyncDatabaseManager.get_database_info()` incluye la contraseña en `connection_params`; no usarlo para nada que se serialice (G11).
- **[probe]**: la prueba de conexión va en un subproceso `spawn`. El hijo se arranca bien desde la API y desde pytest, pero **no** desde un script leído por stdin (`python -`): `spawn` reimporta `__main__` desde una ruta. Para probar a mano, guardar el script en un fichero con guarda `if __name__ == "__main__"`.
- **[bench]**: el SQL Server bench de este equipo publica el **51833** (no el 51433 del compose): pasar `UTIL_BBDD_BENCH_MSSQL_PORT=51833`. Oracle usa `service_name=FREEPDB1` y usuario `bench`; SQL Server, usuario `sa` y BD `bench`.
- **[bench-password]**: `UTIL_BBDD_BENCH_PASSWORD` es variable de usuario de Windows; si VS Code no se ha reiniciado no está en el entorno: cargarla solo en el comando (`$env:X=[Environment]::GetEnvironmentVariable("X","User")`) y borrarla después, sin imprimirla.
- **[docker-host]**: desde el contenedor `web`, los bench se alcanzan con `host.docker.internal` (resuelve a una IPv6 ULA y una IPv4 privada), que debe estar en la allowlist; `127.0.0.1` es el propio contenedor.
- **[allowlist]**: con la allowlist vacía ninguna conexión de red se prueba (`not_allowed`); un host que no resuelve da `connection_failed`. En tests de API se usan IP literales (`10.1.2.3`) para no depender del DNS; en E2E, `203.0.113.10` (RFC 5737).
- **[frontend-tests]**: jsdom necesita, además de los stubs de la Fase 1, `document.fonts` (el `Textarea` con autosize de Mantine) y `Element.prototype.scrollIntoView`; ambos en `src/test/setup.ts`. El `Select` de Mantine tiene rol `combobox`.
- **[rhf-zod]**: no hay `@hookform/resolvers`: usar `components/zodResolver.ts` con `useForm<Entrada, unknown, Salida>`; el formulario de conexión edita todos los parámetros como texto y el esquema de `connectionSchema.ts` los convierte al tipo del catálogo.
- **[imagen]**: con la Fase 2 la imagen runtime mide 768 MB; el bundle principal del frontend, 479 kB (cerca del aviso de 500 kB: nuevas páginas con `lazy`).

## Veredicto final
Veredicto: CLOSED (Fase 2 cumplida; DoD común y de la fase verificadas, con integración y E2E contra motores reales)
Pendientes al cierre:
- Riesgos residuales:
  - *DNS rebinding* entre la comprobación de la allowlist y la conexión del driver (documentado).
  - El readiness muestra rutas absolutas del servidor en el hallazgo `database` de SQLite (información interna menor).
- Matriz de capacidades: documentación, grafos, comparación, volcado y bulk se añadirán al verificarlos en las fases
  5–9.
- El CI no ejecuta las pruebas de integración ni Playwright (manuales).
- Datos de prueba en el volumen `data`: admin `e2e-admin` y usuarios `e2e-…` de la Fase 1; las conexiones y
  destinos E2E se borran en cada prueba.
- Sin commit (pendiente de petición). Siguiente paso: `/phase 3`.
