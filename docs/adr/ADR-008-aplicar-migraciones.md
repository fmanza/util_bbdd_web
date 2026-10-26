# ADR-008 — Aplicar migraciones DDL en una base de datos destino

- **Estado**: Aceptado
- **Fecha**: 2026-10-22

## Contexto

La Fase 7 es la primera que **escribe** en una base de datos destino. `MigrationPlan.execute` de util_bbdd:

- aplica las sentencias una a una con `commit` tras cada una y **no es atómico**: si una falla, las anteriores quedan
  aplicadas (en MySQL, MariaDB y Oracle el DDL además hace commit implícito);
- no tiene modo seco propio; `validate_views` deshace una transacción en PostgreSQL y SQL Server y solo comprueba
  sintaxis en el resto;
- se niega a ejecutar con avisos `ERROR`, pero no con FK entre tipos distintos, que el destino puede rechazar (G28);
- `MigrationPlan` no se serializa ni se reconstruye (G26).

La regla 6 de SHARED exige rol autorizado, conexión no `read_only`, modo seco previo y confirmación explícita.

## Decisión

Tres pasos, cada uno una ejecución con su auditoría:

1. **`migrate_plan`** (editor): solo lee el origen y guarda `plan.json` (tablas, tipos, avisos, sentencias y el
   **SHA-256 de las sentencias**) y el script SQL.
2. **`migrate_apply` en modo seco**: vuelve a planificar y exige el **mismo hash** (el origen no ha cambiado desde
   el plan revisado), comprueba que ninguna tabla del plan exista ya como tabla o vista en el destino, valida las
   vistas y detecta FK entre tipos distintos. No deja cambios.
3. **`migrate_apply` aplicando**: exige un modo seco **correcto** del mismo plan y destino de **menos de 60 minutos**
   y `confirm` igual al alias del destino; vuelve a comprobar hash y conflictos y llama a `plan.execute` con un
   `JsonLinesAuditSink` (`outputs/audit/migracion.jsonl`).

Quién y dónde, comprobado **al encolar** (`domain/runs/migrations.py`) y otra vez en el worker:

- permiso por usuario **`can_apply_ddl`** (lo concede un admin) **y** rol `owner` del proyecto;
- conexión destino del proyecto **no `read_only`** y del motor del plan;
- plan sin avisos `ERROR` y, con destino MariaDB/MySQL, sin FK entre tipos distintos (`fk_blocking`);
- ninguna otra `migrate_apply` activa sobre el mismo destino en el proyecto;
- `migrate_apply` no se relanza ni sale en el formulario genérico, y **no se cancela en curso** (409; en cola sí):
  matar el subproceso dejaría el destino a medias y sin informe.

El worker vuelve a comprobar permiso, rol owner, que la conexión destino siga en el proyecto, no sea `read_only` y
sea del motor del plan. Los conflictos se buscan en `pg_schema` cuando el destino es PostgreSQL con ese schema.

En la web, el panel *Aplicar* del plan exige elegir destino, lanzar el modo seco y, en un modal, marcar «entiendo que
no es atómico» y escribir el alias.

## Consecuencias

- Un fallo a medias deja el destino parcialmente migrado: el informe dice qué sentencia falló (de la auditoría),
  cuántas quedaron aplicadas y el mensaje del motor recortado. Deshacerlo es manual.
- Volver a planificar en cada paso cuesta una lectura del catálogo de origen, a cambio de aplicar exactamente lo
  revisado.
- Cambiar los permisos, el rol, el `read_only` o el motor de la conexión entre encolar y ejecutar se detecta en el
  worker.
- Un timeout (`UBW_JOB_TIMEOUT_SECONDS`) sí puede cortar una aplicación: lo aplicado queda en `migracion.jsonl`.
- Deuda conocida: el modo seco se asocia al destino por alias (no por id de conexión) y la comprobación de
  «ninguna otra aplicación activa» no es atómica frente a dos peticiones simultáneas.

## Alternativas descartadas

- **Aplicar las sentencias guardadas** sin volver a planificar: exigiría la función privada de ejecución de
  util_bbdd y aplicaría un plan obsoleto si el origen cambió.
- **Permiso solo por rol del proyecto** (owner): un owner cualquiera podría escribir en una BD de producción
  compartida; el permiso global lo decide un admin.
- **Transacción alrededor de todo el script**: imposible en MySQL, MariaDB y Oracle (commit implícito del DDL).

## Enmienda (2026-10-26): util_bbdd 4.3.0

- **FK con tipos coherentes (G28, W-M2)**: util_bbdd da a cada columna FK el tipo destino de la columna referenciada
  (`FK_TYPE_ALIGNED`, `INFO`) o bloquea el plan (`FK_TYPE_UNRESOLVED`, `ERROR`). `fk_mismatches` y `fk_blocking` **se
  mantienen** como defensa: los planes guardados antes de la 1.3.0 se siguen bloqueando con destino MariaDB/MySQL.
- **Aplicar el plan revisado sin replanificar (G26, W-M3)**: `migrate_plan` guarda además
  `outputs/plan/migration_plan.json` (`MigrationPlan.to_dict()`). `migrate_apply` lo reconstruye con `from_dict()`
  (que ya exige el `statements_sha256` guardado) y comprueba que su hash sea el `statements_hash` de `plan.json`, el
  que se revisó en el visor; no vuelve a leer el origen. Así se cumple la alternativa que se descartó al principio
  («aplicar las sentencias guardadas») sin usar funciones privadas. Los planes anteriores a la 1.3.0 (sin ese fichero)
  se siguen replanificando como antes. Un plan que otra versión de util_bbdd no reconstruye termina en `plan_changed`.
- **Destino con `check_target` (G27, W-M3)**: los conflictos incluyen ahora las **vistas** del plan que ya existen (en
  MySQL/MariaDB `CREATE OR REPLACE VIEW` las sustituía sin avisar); la validación de vistas sale del mismo
  `TargetCheck`. El informe de una aplicación fallida toma la sentencia, su posición y las aplicadas de
  `MigrationStatementError` en lugar de leer el rastro de auditoría, que se sigue escribiendo.
- El modo seco obligatorio de menos de 60 minutos y la doble confirmación (casilla y alias) **no cambian**.
- **Progreso y cancelación entre sentencias (G1, W-M4)**: `execute(on_progress=, cancel_token=)` con el puente
  `RunProgress` (ADR-002): un evento por sentencia. `migrate_apply` **deja de ser no cancelable en curso**: cancelar
  (con confirmación en la UI) pone el token y util_bbdd para antes de la siguiente sentencia; el informe lleva
  `cancelled` y las aplicadas, y el run termina `cancelled`. El worker **no termina nunca** el subproceso de una
  `migrate_apply` por una cancelación (`CANCEL_BETWEEN_STEPS_ONLY`), así que no se corta una sentencia a medias; el
  `job_timeout` sí, como antes. El modo seco comprueba la cancelación al terminar. El volcado y la carga siguen sin
  cancelarse en curso (ADR-009).
