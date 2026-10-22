# TRACEABILITY

## Session metadata
- id: 2026-10-22-fase4
- fecha: 2026-10-22
- rama: develop
- skill: phase
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION (Fase 4 del ROADMAP)

## Prompt issued
`/phase 4: explorador de metadatos, con árbol schema → tablas, detalle de tabla, queries nombradas y SQL libre
restringido`. Respuestas: permiso por usuario, `sqlglot` directa, alcance completo. Tras AUDIT_PLAN: «IMPLEMENT,
pregunta lo necesario» → CRUD de queries en la web, SQL Server con aviso, mensaje del motor recortado.

## Context supplied
- Ver `00_CONTEXT_SNAPSHOT.md`.

## AI output summary
- PLAN y AUDIT_PLAN: firmas verificadas; hallazgos G17–G20; `GO_CONDICIONAL` con tres decisiones, que tomó el
  usuario.
- Backend:
  - `sqlglot` directa. Ajustes `UBW_METADATA_TIMEOUT_SECONDS`, `UBW_QUERY_TIMEOUT_SECONDS` y `UBW_QUERY_MAX_ROWS`.
  - Migración `0005`: `users.can_run_sql` con `server_default`, probada con usuarios existentes; `metadata_cache` y
    `named_queries`.
  - Capa anticorrupción:
    - `isolated.py`: subproceso genérico; `probe.py` se migró a él.
    - `metadata.py`: schemas desnormalizados en Oracle, snapshot serializado, DDL.
    - `sql.py`: guardián, transacción de solo lectura por motor, `fetchmany`, queries nombradas con un `queries_file`
      temporal + `resolve_query`, serialización y mensaje del motor saneado.
  - `domain/explorer/` (`metadata.py`, `sql.py` y `errors.py`); `probe_slot()` compartido; invalidación de la caché
    al editar la conexión; `can_run_sql` en usuarios, `Me` y `UserOut`.
  - Routers `explorer` (metadatos, queries por conexión, SQL por proyecto) y `admin_queries`.
- Hallazgos corregidos gracias a la integración contra los bench:
  - Oracle devolvía los schemas en minúsculas (normalización de SQLAlchemy) → `denormalize_name`, solo si
    `requires_name_normalize`.
  - MySQL ignora el `REFERENCES` escrito en la columna → test con `FOREIGN KEY` de tabla.
  - ORA-01466 en tablas recién creadas → espera en el test. Además, el test de escritura ahora comprueba el error
    concreto de solo lectura de cada motor, porque antes pasaba por un error distinto.
- Corrección en el frontend de la Fase 3 detectada por el E2E con carga: un evento SSE `run` terminal cerraba la
  fuente antes de `end` y los artefactos no se recargaban. Se corrigió y tiene test de regresión. También se hizo
  idempotente el paso de allowlist del E2E del bench.
- Tests:
  - Backend: 161 nuevos (357), de ellos 147 casos del guardián con evasiones; API con SQLite real (14) y
    regresiones.
  - Integración: 15 nuevos (26) contra PostgreSQL, MySQL, MariaDB, SQL Server y Oracle, incluido el bloqueo real de
    escritura.
  - Vitest: 8 nuevos (60).
  - E2E: `explorer.spec.ts` con la BD de ejemplo `e2e/fixtures/tienda.sql`.
- Frontend:
  - `features/explorer/` (`ExplorerPage`, `ObjectDetail`, `NamedQueriesPanel`, `SqlConsole`, `useExplorer`).
  - `components/ResultTable.tsx` y `features/admin/QueriesPage.tsx`.
  - Pestaña SQL del proyecto, botón *Explorar*, interruptor `can_run_sql` e i18n.
- Docs: guía `explorador.md`, GAPS G17–G20, arquitectura, despliegue (usuarios de BD de solo lectura), solución de
  problemas, README.
- AUDIT_CODE:
  - Backend local y en la imagen `backend-dev`: ruff, `mypy`, pytest (357) y contrato OK.
  - Integración: 26/26.
  - Frontend: format, lint, tsc, Vitest (60) y build OK; bundle de 488 kB; `gen:api` estable.
  - Imagen 0.5.0: web y worker sanos, migración 0004 → 0005; 768 MB.
  - Playwright: 12/12, y 24/24 con `--repeat-each=2`.
  - Salidas en `build/logs/fase4_*.txt`.
- VERSION: 0.5.0, CHANGELOG, ROADMAP, `.ai/product.md`, sesión e `INDEX.md`.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | conversación de la sesión | emitido (GO_CONDICIONAL, condiciones resueltas) |
| Capa anticorrupción | `backend/app/integrations/util_bbdd/{isolated,metadata,sql}.py` | completado |
| Dominio y API | `backend/app/domain/explorer/`, `backend/app/api/v1/{explorer,admin_queries,schemas_explorer}.py` | completado |
| Migración | `backend/alembic/versions/0005_metadata.py` | completado |
| Tests | `backend/tests/{unit/test_sql_guard.py,api/test_explorer.py,integration/test_bench_explorer.py}` | completado |
| Frontend | `frontend/src/features/explorer/`, `features/admin/QueriesPage.tsx`, `components/ResultTable.tsx` | completado |
| E2E | `frontend/e2e/explorer.spec.ts`, `frontend/e2e/fixtures/tienda.sql` | ejecutado |
| Docs | `docs/guides/explorador.md`, GAPS, guías, CHANGELOG, ROADMAP | completado |

## Directrices para Futuras IAs
- **[util_bbdd-queries]**: util_bbdd no trae queries registradas y `resolve_query` interpola con `str.format` (G18). La web guarda las plantillas en `named_queries`, escribe un `queries.json` temporal por ejecución en el subproceso y exige que **todo** valor de parámetro cumpla `PARAM_VALUE` (identificador o número).
- **[sql-guard]**: `app/integrations/util_bbdd/sql.py::check_read_only` es la única puerta del SQL de usuario. Si se añade un motor, hay que añadir su dialecto a `DIALECTS` y su sentencia a `_READ_ONLY_STATEMENTS`, y probar en el bench con un `INSERT` que esquive el guardián, verificando el **mensaje** de solo lectura (no basta con que falle).
- **[read-only-por-motor]**: en MySQL/MariaDB, `SET TRANSACTION READ ONLY` afecta a la **siguiente** transacción (por eso hay un `ROLLBACK` previo). En Oracle, una transacción `READ ONLY` da ORA-01466 con tablas creadas segundos antes. SQLite usa `PRAGMA query_only`. SQL Server no tiene modo de solo lectura.
- **[oracle-nombres]**: SQLAlchemy normaliza a minúsculas los nombres de Oracle; con util_bbdd hay que usar el nombre real (`dialect.denormalize_name`, solo si `dialect.requires_name_normalize`).
- **[mysql-fk]**: MySQL/MariaDB ignoran `REFERENCES` en la definición de columna; las FK de prueba van con `FOREIGN KEY (…) REFERENCES …` a nivel de tabla.
- **[isolated]**: toda tarea nueva de util_bbdd que conecte con una BD destino debe ir por `isolated.run_isolated("módulo:función", kwargs, timeout=…)` y por `probe_slot()` en el dominio. Solo `PublicError` deja pasar un mensaje al usuario.
- **[frontend-sse]**: en `useLiveRun`, un evento `run` con estado terminal recarga el detalle y cierra la fuente; no hay que depender de `end`, porque el `useEffect` se desmonta al cambiar el estado.
- **[e2e-paralelo]**: los E2E corren en paralelo (`fullyParallel`). Los recursos compartidos (p. ej. la entrada `host.docker.internal` de la allowlist) se tratan de forma idempotente y sin limpieza. Conviene comprobar la estabilidad con `--repeat-each=2`.
- **[e2e-sqlite]**: `explorer.spec.ts` necesita `UBW_E2E_SQLITE=1` y la BD de `e2e/fixtures/tienda.sql` copiada con `docker compose cp … web:/data/files/e2e-tienda.db`.
- **[bundle]**: el bundle principal está en 488 kB (aviso de Vite a 500 kB). Lo nuevo debe ir en rutas `lazy` y no hay que importar componentes de páginas desde `Layout`.

## Veredicto final
Veredicto: CLOSED (Fase 4 cumplida; DoD común y de la fase verificadas contra SQLite real, 5 motores bench y E2E)
Pendientes al cierre:
- Riesgos residuales:
  - Funciones con efectos dentro de un `SELECT` en SQL Server (sin transacción de solo lectura; mitigado con un
    usuario de BD solo `SELECT`).
  - Consultas que siguen en el servidor tras matar el subproceso (salvo PostgreSQL, que tiene `statement_timeout`).
- Datos de prueba en el volumen `data`: una conexión `e2e-tienda-…`, una query `e2e_pedidos_…` y un proyecto
  `e2e-sql-…` de una ejecución E2E interrumpida, y `host.docker.internal` en la allowlist.
- El CI no ejecuta Playwright ni la integración.
- Sin commit (pendiente de petición). Siguiente paso: `/phase 5` (documentación y grafos).
