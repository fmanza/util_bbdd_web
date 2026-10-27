# ADR-009 — Volcado de datos en una base de datos destino

- **Estado**: Aceptado
- **Fecha**: 2026-10-22

## Contexto

La Fase 8 copia **filas** de una conexión a otra con `DumpOrchestrator` de util_bbdd. A diferencia de la migración
DDL (ADR-008), el volcado:

- desactiva las **constraints** del destino durante la carga (SQL Server, Oracle, PostgreSQL, MySQL/MariaDB) y las
  reactiva al final; si el proceso muere a mitad, no se restauran (G31);
- puede **vaciar** las tablas destino (`truncate_target`, `True` por defecto en util_bbdd: G30);
- es transaccional por tabla y *best-effort* entre tablas;
- no ofrece vista previa pública del orden de carga (G29);
- devuelve los errores de tabla con el texto de SQLAlchemy, **incluidos los parámetros** (filas del origen).

## Decisión

Mismo modelo que ADR-008, con un permiso propio:

1. **`dump_preview`** (editor, solo lectura) es el **modo seco**: orden de carga por FK y ciclos (réplica exacta de
   `util_bbdd.dump._fk_graph.topological_sort` con el `Inspector` de SQLAlchemy), filas en origen y destino, columnas
   omitidas u obligatorias sin origen, FK hacia tablas fuera del volcado y avisos. Guarda una **huella de estructura**
   (tablas, destino, columnas y orden; no las filas, que cambian).
2. **`dump_apply`** (`form=false`) solo referencia la vista previa: usa **sus** parámetros. Al encolar exige permiso
   **`can_write_data`** (lo concede un admin) **y** rol owner; vista previa correcta de **menos de 60 minutos**;
   destino del proyecto **no `read_only`** y del mismo motor; `confirm` = alias del destino; si vacía el destino,
   `confirm_truncate` = **«VACIAR»**; las conexiones de la vista previa siguen siendo **las mismas** (se guarda su
   id: un alias reasignado a otra conexión no vale); ninguna otra escritura (volcado o migración) activa sobre ese
   destino. El worker lo vuelve a comprobar y **recalcula la estructura**: si cambió, aborta con `preview_changed`
   antes de escribir.
3. La web pasa siempre `truncate_target` explícito (desactivado por defecto en el formulario) y guarda solo la
   **primera línea** de cada error (`_engine_message`), sin los `[parameters]` de SQLAlchemy y con los valores que
   algunos motores ponen en ella enmascarados (`redact_values`: «Duplicate entry '…'», «duplicate key value is
   (…)»). Es una lista de patrones conocidos (G34): un formato nuevo de un driver podría escaparse.
4. Un volcado **en curso no se cancela** (409; en cola sí). El resultado (`outputs/dump/result.json`), el Excel de
   util_bbdd, la auditoría (`volcado.jsonl`) y, con `on_error="isolate"`, `rechazos.csv` quedan como artefactos.
5. `audit_log` registra en cada volcado la vista previa, origen, destino, tablas, si vacía y el modo de errores.

## Consecuencias

- Un timeout (`UBW_JOB_TIMEOUT_SECONDS`) puede cortar el volcado con constraints desactivadas en SQL Server u Oracle:
  hay que revisarlas a mano (la guía lo explica).
- `rechazos.csv` contiene datos de negocio (las filas apartadas), visibles para los miembros del proyecto como el
  resto de artefactos.
- Limitaciones de util_bbdd verificadas: con destino Oracle `isolate` no aparta la PK duplicada (G32); SQLite → SQLite
  no carga fechas guardadas como texto (G33). La vista previa avisa de ambas.

## Alternativas descartadas

- **Reutilizar `can_apply_ddl`**: escribir datos y cambiar estructura son riesgos distintos y los conceden personas
  distintas.
- **Volcado sin vista previa previa** (confirmación en el formulario): no habría una revisión de qué se va a escribir
  ni detección de cambios de estructura.
- **Permitir cancelar**: matar el proceso deja tablas a medias y constraints desactivadas.

## Enmienda (2026-10-27): util_bbdd 4.4.0

- **Vista previa con `plan()` (G29, W-V1)**: `dump_preview` toma el orden de carga, los ciclos, las columnas omitidas,
  las obligatorias sin origen y las FK hacia tablas fuera del volcado de `DumpOrchestrator.plan()`, con el mismo
  `DumpConfig` que el volcado; ya no replica `topological_sort`. Los recuentos de filas siguen siendo de la web (`plan()`
  no cuenta). La huella de estructura y la posición de cada tabla (su índice en el orden de carga) no cambian.
- **Avance por tabla y cancelación entre lotes (G1, G6, W-V2)**: `run(on_progress=, cancel_token=)` con `DumpProgress`
  (puente `RunProgress`, ADR-002): el run muestra tablas terminadas y filas escritas de la tabla en curso. El punto 4 de
  la decisión **cambia**: un volcado en curso **se puede cancelar** (con confirmación en la UI). util_bbdd para entre
  lotes, deshace la tabla en curso, reconstruye índices y reactiva constraints, y lanza `OperationCancelledError` sin
  `DumpResult`; `result.json` lleva `cancelled` y las tablas terminadas, que quedan cargadas, y el run termina
  `cancelled`. El worker **no termina nunca** el subproceso de un `dump_apply` por una cancelación
  (`CANCEL_BETWEEN_STEPS_ONLY`, como `migrate_apply`); el `job_timeout` sí. `volcado.jsonl` recibe el evento de cada
  tabla al terminarla. La carga bulk sigue sin cancelarse en curso (ADR-010).
- **Constraints sin restaurar (G31, W-V3)**: con destino SQL Server, PostgreSQL u Oracle util_bbdd escribe
  `constraints_journal.json` en `output_dir` antes de desactivar nada; si el proceso muere o alguna constraint no se
  reactiva, el diario queda. La web conserva entonces la carpeta `work/` del run (no es artefacto), con el diario y
  `target.json` (alias e id de la conexión destino, que el job anota antes de escribir). La operación nueva
  **`dump_restore`** (`form=false`) llama a `restore_constraints` con los **mismos controles que el volcado**:
  `can_write_data` + owner, la conexión destino con el mismo id, no `read_only` y del mismo motor que el diario,
  `confirm` = alias, ninguna otra escritura activa sobre el destino; se audita (`run.create` con `dump_restore`) y el job
  lo vuelve a comprobar. El worker la **encola sola** al cerrar un `dump_apply` cuyo proceso murió (timeout, caída,
  huérfano, parada) si el diario existe, en nombre del usuario del volcado (auditada como del worker); si los controles
  ya no se cumplen, falla y queda la acción manual. Mientras quede un diario: un `dump_apply` nuevo sobre ese destino
  responde 409 y el volcado no se purga (ni a mano, ni por retención, ni por cuota). La consecuencia «hay que revisarlas
  a mano» tras un timeout deja de aplicarse salvo en MySQL/MariaDB, donde la desactivación es de la sesión.
