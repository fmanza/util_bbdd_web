# TRACEABILITY

## Session metadata
- id: 2026-10-22-fase3
- fecha: 2026-10-20 → 2026-10-22
- rama: develop
- skill: phase
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION (Fase 3 del ROADMAP)

## Prompt issued
`/phase 3: proyectos con miembros, motor de ejecuciones con worker y un subproceso por job, SSE para el progreso y
workspace por ejecución.` Respuestas: alcance completo, sin dependencias, sin mejoras. Tras AUDIT_PLAN: «IMPLEMENT».
Durante IMPLEMENT: «continua / puedes continuar en la nube / continua».

## Context supplied
- Ver `00_CONTEXT_SNAPSHOT.md`.

## AI output summary
- PLAN + AUDIT_PLAN: cola propia (opción b de ADR-002), SSE nativo de FastAPI, ULID propio; `GO_CONDICIONAL` con 4
  desviaciones aceptadas: purga manual + `GET /runs` global, worker fuera de perfil, Markdown como texto y admin sin
  acceso a proyectos ajenos.
- Se siguió en local (no en la nube): la fase dependía de cambios sin commit, Docker y los bench locales.
- Backend:
  - Configuración `UBW_WORKER_*`, `UBW_JOB_TIMEOUT_SECONDS`, `UBW_MAX_QUEUED_PER_USER`, `UBW_USER_QUOTA_MB` y
    `UBW_RUN_RETENTION_*`; `core/ulid.py`.
  - Modelos `Project`, `ProjectMember`, `ProjectConnection`, `Run`, `Artifact` y `Worker`; migración `0004`
    (autogenerada y revisada; `alembic check` y upgrade/downgrade OK).
  - `workspace/layout.py`: rutas solo con IDs, `safe_path`, manifiesto atómico, escaneo de artefactos y ZIP en
    *streaming*.
  - `integrations/util_bbdd/audit_sink.py` (`RunAuditSink`).
  - `domain/projects` (roles, miembros y alias) y `domain/runs` (catálogo `noop`, encolar, cancelar, relanzar, purgar,
    retención, cuota, estado del worker).
  - `jobs/` (`context`, `operations/noop`, `runner` con `finalize_run`, `queue` con `UPDATE … RETURNING`, `worker` con
    latidos, cancelación, timeout, `worker_crash`, huérfanos, retención y SIGTERM multiplataforma).
  - Routers `projects`, `runs` (historial, 202, SSE, artefactos con CSP `sandbox`, ZIP) y `operations`;
    `/api/health` con `worker`.
- Correcciones durante IMPLEMENT y AUDIT_CODE:
  - El 404 de SSE se lanzaba dentro del generador (salía como 500) → se pasó a una dependencia previa.
  - El manifiesto con `datetime` no se podía guardar en la columna JSON → fechas ISO.
  - `FileResponse` sin `filename` no enviaba `Content-Disposition: inline`.
  - En Linux `C:\…` es un nombre relativo válido → `safe_path` rechaza `\` y letras de unidad en cualquier SO.
  - Frontend: `setState` en render → hook `useLiveRun`; `Select` buscable de Mantine → `NativeSelect` (opciones
    inaccesibles en jsdom); `asyncUtilTimeout` a 3 s por *flakiness* de la suite en paralelo.
- Tests: 45 nuevos en backend (196): unitarios de ULID, workspace, ZIP, contrato de `RunAuditSink` y operaciones;
  capas en el test de arquitectura; API de proyectos; motor con subprocesos reales (éxito, fallo, cancelación en curso,
  timeout, hijo matado, huérfanos, SQLite real, secreto nunca en ficheros, relanzar, purgar, retención, health).
  13 nuevos en Vitest (52), con `EventSource` simulado. E2E `runs.spec.ts` (2 flujos).
- Docker y CI: el worker arranca con `docker compose up` (`stop_grace_period: 30s`); el CI espera `"worker":"ok"`.
- Docs: guía `proyectos_y_ejecuciones.md`; notas en ADR-002 y ADR-005; arquitectura, `.ai/architecture.md`,
  despliegue, incorporación, solución de problemas, README.
- AUDIT_CODE:
  - Backend local: ruff, `mypy` (ahora también sin `--platform` en Windows), pytest (196 passed, 11 skipped) y
    `export_openapi --check` OK. En la imagen `backend-dev` (Linux), OK tras la corrección de `safe_path`.
  - Integración contra los bench: 11/11.
  - Frontend: prettier, eslint, tsc, Vitest (52) y build OK; bundle principal de 484 kB; `gen:api` estable.
  - `docker compose build` + `up`: web *healthy*, migración 0003 → 0004, worker iniciado, `/api/health` → 0.4.0 con
    `worker: ok`; imagen de 768 MB (sin cambios).
  - Playwright: 11/11 sobre la imagen final. Verifica el progreso en vivo, que el `<script>` del HTML de ejemplo **no**
    se ejecuta en el `iframe`, el ZIP descargado, relanzar y cancelar en curso.
  - Parada con SIGTERM: «Worker detenido» y health → `absent`.
  - Contraseña del bench: 0 apariciones en los logs de web y worker.
  - Salidas en `build/logs/fase3_*.txt`.
- VERSION: 0.4.0 (backend, `uv.lock`, `package.json`, `package-lock.json`); CHANGELOG, ROADMAP (Fase 3 cerrada),
  `.ai/product.md`, sesión e `INDEX.md`.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | conversación de la sesión | emitido (GO_CONDICIONAL, aprobado) |
| Modelos + migración | `backend/app/db/models.py`, `backend/alembic/versions/0004_projects_runs.py` | completado |
| Workspace | `backend/app/workspace/layout.py` | completado |
| Dominio | `backend/app/domain/{projects,runs}/` | completado |
| Jobs y worker | `backend/app/jobs/{context,queue,runner,worker}.py`, `jobs/operations/` | completado |
| API | `backend/app/api/v1/{projects,runs,operations,schemas_projects}.py`, `api/health.py` | completado |
| Tests backend | `backend/tests/{unit,api}/` | completado (196 + 11 de integración) |
| Frontend | `frontend/src/features/{projects,runs}/`, `src/test/{eventSource,fixtures_runs}.ts` | completado (52 tests) |
| E2E | `frontend/e2e/runs.spec.ts` | ejecutado (11/11 en total) |
| Docker/CI | `docker-compose.yml`, `.github/workflows/ci.yml` | completado (CI remoto no ejecutado) |
| Docs | `docs/guides/proyectos_y_ejecuciones.md`, ADR-002/005, guías, CHANGELOG, ROADMAP | completado |

## Directrices para Futuras IAs
- **[jobs]**: una operación nueva se registra en dos sitios: el **modelo de parámetros** en `app/domain/runs/operations.py` (`OPERATIONS`, `extra="forbid"`; los alias de conexión se marcan con `json_schema_extra={"ubw_kind": "connection"}`) y la **implementación** `run(ctx: JobContext)` en `app/jobs/operations/__init__.py` (`IMPLEMENTATIONS`). Los errores para el usuario se lanzan como `JobError(code, message)`.
- **[jobs-subproceso]**: el hijo (`runner.run_job`) solo recibe el `run_id` y hereda el entorno; los ajustes los lee con `get_settings()`. En los tests, `monkeypatch.setenv` llega a los hijos, pero `monkeypatch.setattr` sobre `Settings` **no** (solo afecta al padre: timeouts, cuota, límite de cola).
- **[jobs-conexiones]**: dentro de un job, `ctx.test_connection(alias)` aplica allowlist y descifrado (`prepare_connection`); las operaciones reales de las fases 4–9 deben obtener los `conn_params` igual y pasar `RunAuditSink(ctx.run_dir / "logs/run.log")` como `audit_sink`.
- **[sse]**: con `response_class=EventSourceResponse` y un generador asíncrono, cualquier excepción dentro del generador ya no puede convertirse en 4xx (sale como 500/`ExceptionGroup`): validar acceso en una **dependencia** (`VisibleRun`) y hacer el acceso a BD con `run_in_threadpool` + `new_session()`.
- **[sqlite-json]**: las columnas `JSON` de SQLAlchemy no serializan `datetime`: el manifiesto (`runs.manifest`) usa fechas ISO (`_iso`).
- **[workspace]**: `safe_path` rechaza `..`, absolutas, `\` y letras de unidad en todos los SO; en Linux `C:\x` sería un nombre relativo válido. Las rutas de artefactos se guardan POSIX relativas a la carpeta del run.
- **[tests-worker]**: `tests/api/test_runs.py` usa `Worker(...).tick()` en bucle con subprocesos *spawn* reales (≈1–2 s por job en Windows, ≈40 s la suite completa); `wait_for(worker, db, run_id, statuses=…)` es el patrón.
- **[frontend-tests]**: `src/test/eventSource.ts` (`stubEventSource()` + `instances.at(-1).emit('run' | 'end', data)` / `fail()`); `stubApi` admite `{ text }` para respuestas `text/plain`. Los `Select` buscables de Mantine no exponen opciones en jsdom: para listas de datos usar `NativeSelect` o probar con valores ya seleccionados.
- **[frontend-fetch]**: fuera del cliente OpenAPI, llamar a `fetch(new Request(new URL(ruta, location.origin), …))`: los stubs de los tests esperan un `Request` y Node no acepta URL relativas.
- **[compose]**: `docker compose up` arranca `web` y `worker`; el worker también ejecuta `alembic upgrade head` en el *entrypoint*, pero espera a `web` sano (`depends_on`), así que nunca migran a la vez.
- **[sesion]**: si el usuario pide «continuar en la nube» con cambios sin commit y validación que depende de Docker/bench locales, explicar que se sigue en local (un agente remoto no ve el árbol de trabajo).

## Veredicto final
Veredicto: CLOSED (Fase 3 cumplida; DoD común y de la fase verificadas con subprocesos, SSE, Docker y E2E reales)
Pendientes al cierre:
- Riesgos residuales:
  - Sin límite de conexiones SSE por usuario (cada una consulta la BD cada segundo; Fase 10).
  - La vista previa de Markdown es texto plano (se renderizará cuando una fase genere Markdown de verdad).
- El CI remoto no se ha ejecutado tras el cambio del worker (`"worker":"ok"`); lo hará el próximo push.
- Datos de prueba en el volumen `data`: `e2e-admin` y usuarios `e2e-…`; los proyectos E2E se borran en cada prueba.
- Sin commit (pendiente de petición). Siguiente paso: `/phase 4` (explorador de metadatos).
