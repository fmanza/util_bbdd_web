# ADR-002 — Ejecución de jobs

- **Estado**: Aceptado (implementado en la Fase 3, 0.4.0; cola opción **b**)
- **Fecha**: 2026-10-19

## Contexto

Documentar, comparar, migrar, volcar y cargar en bulk pueden tardar minutos y consumir mucha memoria. util_bbdd no
ofrece callbacks de progreso ni cancelación (GAPS G1) y `DatabaseDocumentation` guarda estado en un atributo de clase
(GAPS G2). No se quiere añadir Redis.

## Decisión

1. Las operaciones de util_bbdd se ejecutan como **jobs** en un proceso **worker** separado de la API (mismo
   contenedor, otro comando: `python -m app.jobs.worker`).
2. **Un subproceso hijo por job**: cancelar es terminar el subproceso; además aísla memoria y estado de clase entre
   ejecuciones de usuarios distintos.
3. **Cola**: tabla `runs` en `config.db` como fuente de verdad (estado, parámetros, progreso). Opciones a confirmar en
   Fase 3: (a) Huey con almacenamiento SQLite como despachador, o (b) cola propia con `UPDATE … RETURNING` atómico
   sobre `runs`. Criterio: menor número de piezas con reintentos y *timeouts* fiables.
4. **Progreso por fases** (preparando, conectando, ejecutando, generando informes, terminado) escrito en `runs` de forma
   agrupada; la API lo emite por SSE.
5. Concurrencia del worker configurable (`UBW_WORKER_CONCURRENCY`, por defecto 2).

## Consecuencias

- Coste de arranque de un proceso por job (aceptable frente a la duración de las operaciones).
- Sin porcentaje real de progreso hasta que util_bbdd resuelva G1.

## Notas de implementación (Fase 3)

- **Cola propia (opción b)**: `runs` es la cola. El worker reclama con un único
  `UPDATE runs SET status='running' … WHERE id = (SELECT … WHERE status='queued' ORDER BY created_at LIMIT 1)
  AND status='queued' RETURNING id` (SQLite ≥ 3.35; la imagen trae 3.40). Huey se descartó: dependencia nueva y una
  pieza más para el mismo resultado.
- **Subproceso por job** con `multiprocessing` *spawn*: el hijo solo recibe el `run_id`, lee la BD y descifra los
  secretos que necesite. Escribe `run.json`, `logs/run.log` (JSON) y `outputs/`, y cierra el run (`finalize_run`).
- **El padre** emite latidos (`workers`, `runs.heartbeat_at`), aplica cancelaciones (`cancel_requested` →
  `terminate`/`kill` → `cancelled`) y timeouts (`UBW_JOB_TIMEOUT_SECONDS` → `job_timeout`), cierra como
  `worker_crash` al hijo que muere sin estado final y, al arrancar, como `interrupted` los runs huérfanos de otro
  worker sin latido. Con SIGTERM termina sus jobs (`interrupted`) y se da de baja.
- **Progreso por fases** (`preparing → connecting → running → reporting → done`) escrito como mucho una vez por
  segundo; la API lo emite por SSE con `EventSourceResponse` nativo de FastAPI (sin dependencias), comprobando el acceso
  antes de abrir el stream.
- `docker compose up` arranca `web` y `worker` (ya no es un perfil); `/api/health` informa `worker: ok|stale|absent`.

## Enmienda (2026-10-26): progreso y cancelación cooperativa con util_bbdd 4.1.0

util_bbdd 4.1.0 publica `util_bbdd.progress` (GAPS G1): las operaciones aceptan `on_progress` y `cancel_token`, avisan
de su avance por unidad de trabajo y paran entre unidades con `OperationCancelledError`.

- **Puente** `app/integrations/util_bbdd/progress.py` (`RunProgress`): cada evento se publica con `ctx.progress`
  (mensaje «Word: 3 de 12 (clientes)» y porcentaje repartido entre las fases) y, como mucho cada 2 s, se lee
  `runs.cancel_requested` (`JobContext.cancel_requested`); si está pedido, cancela el token.
- **Parada cooperativa**: la operación termina la unidad en curso y lanza `OperationCancelledError`; el job la
  convierte en `JobError("cancelled")` y el runner cierra el run como `cancelled`.
- **El worker** deja a las operaciones cooperativas (`COOPERATIVE_OPERATIONS`: `documentation` y
  `relationship_graph`; el grafo de una sola tabla es una unidad y no para a mitad)
  `COOPERATIVE_CANCEL_GRACE` (60 s) antes de terminar el subproceso; si no paran a tiempo, `terminate`/`kill` como
  antes. El resto de operaciones no cambia. El subproceso por job se mantiene (aislamiento de memoria y estado).
- Las demás operaciones se suman al conectar util_bbdd su progreso (plan de huecos, olas 2-5). Con util_bbdd 4.2.0
  se suma `compare` (fases `metadata`, `tables`, `views` y `routines`); los informes, que se generan después, no se
  interrumpen.

