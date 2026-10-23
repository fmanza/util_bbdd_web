# TRACEABILITY

## Session metadata
- id: 2026-10-22-fase8
- fecha: 2026-10-22 → 2026-10-23
- rama: develop
- skill: phase
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION (Fase 8 del ROADMAP)

## Prompt issued
`/phase 8 pregunta lo que necesites`. Respuestas: permiso `can_write_data` + owner, vaciar con confirmación extra, no
cancelar en curso, alcance completo + aislar rechazos + repartir el bundle. Tras AUDIT_PLAN: «IMPLEMENT, pregunta lo
que necesites» → vendors + i18n por ruta.

## Context supplied
- Ver `00_CONTEXT_SNAPSHOT.md`.

## AI output summary
- PLAN y AUDIT_PLAN: `GO_CONDICIONAL` con dos condiciones, verificadas con util_bbdd real al empezar:
  - el orden de la vista previa es **idéntico** al `load_order` de util_bbdd (con y sin ciclos y con nombres de otra
    caja);
  - `error_msg` trae los parámetros de SQLAlchemy (**filas del origen**), así que se guarda solo la primera línea
    saneada (G34).
- Backend:
  - Migración `0007` (`users.can_write_data`).
  - `integrations/util_bbdd/dump.py`: `load_order` (réplica de `_fk_graph`), `build_preview`, `structure_hash`,
    `run_dump` (con `truncate_target` siempre explícito, rechazos, auditoría, Excel) y `result_to_dict` saneado.
  - `domain/runs/dumps.py` (`check_apply`, `load_preview`, `load_result`) enganchado en `enqueue`.
    `NOT_CANCELLABLE_RUNNING` es común a `migrate_apply` y `dump_apply`.
  - Jobs `jobs/operations/dump.py`, con nueva comprobación en el worker y `preview_changed`.
  - Endpoints `/dump-preview` y `/dump-result`; tipos de artefacto `dump` y `rejects`.
- Hallazgos durante IMPLEMENT:
  - Con destino Oracle, `isolate` no aparta la PK duplicada (G32).
  - SQLite → SQLite falla en columnas de fecha guardadas como texto (G33; lo descubrió el E2E).
  - Ambos se avisan en la vista previa y tienen test que documenta el comportamiento real.
- Bundle: la medición con sourcemap mostró que lo dominan react-dom, react-router y Mantine, no las traducciones (lo
  dicho en la Fase 7 era incorrecto). Se separaron `vendor-react`/`vendor-app` con `codeSplitting.groups` (solo
  librerías ya iniciales) y las traducciones en `es/core.json` + `es/features.json`, cargadas con la primera ruta
  lazy (`withMessages` en el router). El chunk principal pasa de 492 kB a 132 kB.
- Frontend: `features/runs/dump/` (`DumpPreviewViewer` con panel y modal de doble confirmación, `DumpResultView`,
  `useDump`) e interruptor *Puede volcar datos*.
- Tests:
  - Backend: 23 nuevos (479), volcados reales SQLite → SQLite en el CI.
  - Integración: 8 nuevos (64) con escritura en 4 combinaciones.
  - Vitest: 10 nuevos (89).
  - E2E: `dump.spec.ts` (SQLite, sin bench).
- AUDIT_CODE:
  - Backend local y en `backend-dev`: 488, ruff, mypy y contrato OK.
  - Frontend: format, lint, tsc, Vitest (89) y build OK (una ejecución tuvo 5 timeouts por carga de CPU; las dos
    siguientes, 89/89; tras la auditoría, 90).
  - Imagen 0.9.0: migración 0006 → 0007; Playwright 29 + 3 omitidos con `--repeat-each=2 --workers=2`; migración 1/1;
    volcado 1/1; integración 64/64.
  - Salidas en `build/logs/fase8_*.txt`.
- `/audit-code` antes del commit: APROBADO CON CONDICIONES → corregido: auditoría con detalles del volcado;
  enmascarado de valores en los errores (H1 confirmado en el bench: MySQL, MariaDB y SQL Server ponían el valor de
  la clave); id de conexión en la vista previa (alias reasignado → 422 al encolar y `preview_changed` en el
  worker); exclusión común migración/volcado por destino (`domain/runs/targets.py`); `work/` en `finally`; patrón
  de tablas sin `.`; test estático de claves i18n del bundle inicial (verificado con una mutación). Tests nuevos:
  9 backend, 5 de integración y 1 de Vitest.
- VERSION: 0.9.0, CHANGELOG, ROADMAP, ADR-009, guías (volcado, usuarios, despliegue, problemas, proyectos),
  arquitectura e instrucciones de frontend (rutas de i18n), GAPS G29–G34, `.ai/product.md`, sesión e `INDEX.md`.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | conversación de la sesión | emitido (GO_CONDICIONAL, condiciones verificadas) |
| Migración Alembic | `backend/alembic/versions/0007_dump.py` | completado |
| Capa anticorrupción | `backend/app/integrations/util_bbdd/dump.py` | completado |
| Dominio, jobs y API | `backend/app/domain/runs/dumps.py`, `backend/app/jobs/operations/dump.py`, `backend/app/api/v1/{runs,schemas_dump}.py` | completado |
| Tests | `backend/tests/{unit/test_dump_units.py,api/test_dump.py,integration/test_bench_dump.py}` | completado |
| Frontend | `frontend/src/features/runs/dump/`, `frontend/src/i18n/{index.ts,es/}`, `frontend/vite.config.ts` | completado |
| E2E | `frontend/e2e/dump.spec.ts`, `frontend/e2e/fixtures/volcado{,_vacio}.sql` | ejecutado |
| Docs | `docs/adr/ADR-009-volcado-de-datos.md`, `docs/guides/volcado.md`, GAPS G29–G34 | completado |

## Directrices para Futuras IAs
- **[dump-orden]**: `integrations/util_bbdd/dump.load_order` replica `util_bbdd.dump._fk_graph.topological_sort` (cola en el orden recibido, dependientes ordenados, ciclos al final). Las tablas elegidas se resuelven a los nombres del catálogo y se pasan ordenadas, como `_get_source_tables`. Si se actualiza util_bbdd, `test_dump_appends_isolates_rejects_and_reports` compara con el `load_order` real.
- **[dump-errores]**: los `error_msg` de util_bbdd (tabla, constraint, PK) traen `[parameters: …]` con filas del origen y, en MySQL/MariaDB y SQL Server, el valor de la clave en la primera línea (G34). Hay que guardarlos siempre con `_clean` (`_engine_message` + `redact_values`). Si aparece un formato nuevo, hay que añadirlo a los patrones y al test de bench.
- **[destino-por-conexion]**: un alias puede reasignarse a otra conexión. Las vistas previas guardan `source_connection_id`/`target_connection_id`, y `dumps.connections_changed` lo comprueba al encolar y en el worker. El modo seco de la migración (ADR-008) sigue asociado por alias: es deuda conocida.
- **[una-escritura-por-destino]**: `domain/runs/targets.active_write` es la única comprobación de concurrencia sobre un destino (migración y volcado). La carga bulk (Fase 9) debe añadirse a `WRITE_OPERATIONS`.
- **[heredoc-escapes]**: los scripts Python con `\b`, `\1` o `'''` dentro de heredocs de bash se corrompen (caracteres de control en el fichero). Hay que escribirlos con Write y, tras editar regex, buscar `[\x01-\x08]` en los ficheros cambiados.
- **[dump-limitaciones]**: Oracle + `isolate` no aparta la PK duplicada (G32) y SQLite → SQLite no carga DATE/DATETIME guardados como texto (G33). Ambos se avisan en la vista previa (`warnings`). Los tests lo documentan: si util_bbdd lo corrige, fallarán y habrá que quitar el aviso.
- **[escritura-bd]**: `migrate_apply` y `dump_apply` siguen el mismo patrón (ADR-008/009). La Fase 9 (carga bulk) debería reutilizarlo: permiso propio o `can_write_data`, owner, modo seco reciente, confirmación, `form=False`, `NOT_CANCELLABLE_RUNNING` y la comprobación en el worker.
- **[i18n]**: las traducciones están en `src/i18n/es/core.json` (lo que se ve sin ruta lazy: login, menú, comunes, home) y `es/features.json` (pantallas). Una clave nueva en un componente que no esté en una ruta lazy va a `core.json`; si no, se verá la clave cruda. i18next fusiona los bundles **dentro** del objeto importado de `core.json` (no hay que compararlo en tests).
- **[bundle]**: Vite 8/Rolldown usa `build.rolldownOptions.output.codeSplitting.groups`. Solo se agrupan librerías que ya carga la entrada: un grupo genérico de `node_modules` metería en la carga inicial `marked`, `diff` y `highlight.js`.
- **[e2e-sqlite]**: `docker compose cp` deja los ficheros como root y el contenedor no tiene `CAP_CHOWN`. Para que la app pueda escribir en una SQLite copiada hay que reescribirla como `app` (`cp f x && mv -f x f` con `docker compose exec web`). Desde Git Bash, `docker compose -f /c/…` falla con `MSYS_NO_PATHCONV=1`: hay que ejecutarlo desde la raíz sin `-f`.
- **[vitest-carga]**: con el stack de Docker arrancado, alguna prueba puede pasar de los 3 s de `asyncUtilTimeout`. Hay que repetir antes de dar un fallo por bueno.

## Veredicto final
Veredicto: CLOSED (Fase 8 cumplida con los dos extras; DoD verificada con escritura real en 4 combinaciones, SQLite en el CI y E2E)
Pendientes al cierre:
- Riesgos residuales:
  - Un timeout puede dejar constraints desactivadas en SQL Server u Oracle (G31).
  - `rechazos.csv` contiene datos de negocio.
  - Limitaciones G32 y G33 de util_bbdd.
- El CI no ejecuta Playwright ni la integración.
- Sin commit (pendiente de petición). Siguiente paso: `/phase 9` (carga bulk).
