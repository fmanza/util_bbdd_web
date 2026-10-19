# ADR-002 — Ejecución de jobs

- **Estado**: Aceptado (implementación en Fase 3; la elección de la cola se confirma en el PLAN de esa fase)
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
