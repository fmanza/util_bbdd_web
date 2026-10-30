# ADR-010 — Carga bulk desde fichero

- **Estado**: Aceptado
- **Fecha**: 2026-10-23

## Contexto

La Fase 9 inserta, actualiza o borra filas de **una tabla** destino a partir de un fichero CSV o Excel que sube el
usuario, con `BulkCrud` de util_bbdd. Comparado con el volcado (ADR-009):

- la entrada es un **fichero no confiable** (tamaño, tipo real, bombas zip, macros, codificaciones);
- update y delete afectan a filas **ya existentes**, identificadas por la clave primaria del fichero;
- `bulk_*_from_df(..., generar_sql=True)` es el **valor por defecto** y escribe el SQL sin ejecutarlo (G35);
- con plan paralelo cada partición es **una transacción**: la carga deja de ser atómica (G36);
- los contadores `rows_committed`/`last_operation_rows_committed` no son fiables (G37).

## Decisión

1. **Subidas** (`POST /api/v1/projects/{id}/uploads`, `multipart/form-data` con `python-multipart`; editores): solo
   `.csv` y `.xlsx`, copia en streaming a un temporal con límite de tamaño (`UBW_UPLOAD_MAX_MB`) y de cuota, y
   comprobación del **contenido real**: CSV sin bytes NUL; xlsx como zip con `xl/workbook.xml`, sin `vbaProject.bin`
   y con tamaño descomprimido acotado (`UBW_UPLOAD_MAX_UNCOMPRESSED_MB`). Se guardan en
   `users/{owner}/projects/{id}/uploads/<ulid>.<ext>` (nunca con el nombre del usuario), cuentan para la cuota, se
   auditan y se borran a los `UBW_UPLOAD_RETENTION_DAYS` salvo que una carga los use. Las filas leídas se limitan a
   `UBW_BULK_MAX_ROWS`.
2. **`bulk_preview`** (editor, `form=false`, lanzado desde la pestaña *Carga*) es el **modo seco**: lee el fichero en
   la web, refleja la tabla (`reflect_table`), resuelve el mapeo (explícito o por nombre sin distinguir mayúsculas) y
   valida: columnas inexistentes, obligatorias ausentes en insert, PK ausente o sin columnas que actualizar en
   update/delete. Cuenta las filas **distintas** del destino que coinciden por PK (lotes de 500, o 200 con PK
   compuesta) y genera el SQL con `generar_sql=True` como artefacto `sql/carga_<op>.sql`. Guarda la huella de
   estructura (operación, tabla, columnas, PK y mapeo), el id de la conexión y el SHA-256 del fichero. No sale en el
   formulario genérico de ejecuciones porque este solo pinta campos `string`, `integer`, `float`, `boolean`,
   `connection` y `template` (plantillas de documento, ADR-011): la vista previa necesita elegir un fichero subido
   (`upload`) y un mapeo de columnas cuyas opciones salen de reflejar la tabla destino. La pestaña *Carga* reúne la subida, el mapeo y el lanzamiento.
3. **`bulk_apply`** (`form=false`) solo referencia la vista previa y exige, como ADR-009: permiso **«Puede escribir
   datos»** (`can_write_data`, el mismo del volcado) y rol owner; vista previa correcta, **sin errores** y de menos de
   60 minutos; mismo fichero y misma conexión; destino no `read_only` y del mismo motor; `confirm` = alias. Además:

    - update y delete: `confirm_rows` = **filas afectadas** de la vista previa; el worker las vuelve a contar antes de
      escribir y aborta con `preview_changed` si ya no coinciden;
    - plan paralelo de más de un hilo: `accept_non_atomic`.

    Una sola escritura (migración, volcado o carga) por destino; en curso no se cancela ni se relanza. El worker
    comprueba todo de nuevo, refleja la tabla y exige la misma huella. Se ejecuta siempre con `generar_sql=False`.

4. El resultado lo calcula la web: filas del destino **antes y después**, coincidencias por PK, `rows_rejected`
   (fiable) y particiones. Errores con la primera línea del motor y los valores enmascarados (`redact_values`, G34).
   Artefactos: `result.json`, `carga.jsonl` (auditoría de util_bbdd) y `rechazos.csv` con «apartar».
5. `audit_log` registra en cada carga la vista previa, el fichero, el destino, la tabla, la operación, las filas
   confirmadas, el modo de errores y si es paralela.

## Consecuencias

- El SQL generado y `rechazos.csv` contienen **datos de negocio** del fichero, visibles para los miembros del
  proyecto como el resto de artefactos; los ficheros subidos también.
- Un proxy inverso debe admitir cuerpos de `UBW_UPLOAD_MAX_MB` (nginx: `client_max_body_size`).
- Una carga paralela que falla a medias deja confirmadas las particiones correctas (`bulk_partial`).
- Con «apartar» en Oracle valen las limitaciones de G32.

## Alternativas descartadas

- **Permiso propio para la carga**: volcado y carga escriben filas con el mismo riesgo; se reutiliza
  `can_write_data` («Puede escribir datos»).
- **Subida en JSON/base64**: un tercio más de tamaño y todo el fichero en memoria; `multipart` permite streaming.
- **Leer el fichero en la capa de integración**: la validación de entrada es del dominio; la integración recibe un
  `DataFrame` y no importa `app.domain` (test de arquitectura).
- **`bulk_preview` en el formulario genérico** (como `dump_preview`): habría que añadirle tipos de campo para ficheros
  subidos y para un mapeo que depende de la tabla, y la subida tendría que vivir en otra pantalla de todas formas.
- **Confiar en `rows_committed`**: verificado incorrecto en la sonda de la fase (G37).

## Enmienda (2026-10-27): util_bbdd 4.4.0

util_bbdd corrige G32 también en `BulkCrud`: con destino Oracle, «apartar» separa la fila con PK duplicada aunque el
lote tenga una sola fila. La consecuencia «con apartar en Oracle valen las limitaciones de G32» deja de aplicarse.

## Enmienda (2026-10-27): util_bbdd 4.5.0

- **Contadores de util_bbdd (G37, W-B1)**: el resultado toma `last_operation_rows_committed` como cifra principal
  («filas confirmadas»). Son filas **enviadas** y confirmadas (incluyen las apartadas y, en update o delete, las claves
  que no existen), no las que la BD modificó. El recuento del destino antes y después se mantiene como **verificación**
  (`verified`): sin rechazos, error ni particiones fallidas, insert crece en las confirmadas, delete decrece en las
  coincidencias por PK y update no cambia el número de filas; si no cuadra, la carga termina bien con un aviso. La
  alternativa descartada «confiar en `rows_committed`» deja de aplicarse como estaba escrita.
- **Modo seco explícito (G35, W-B1)**: la vista previa llama con `dry_run=True` y la carga con `dry_run=False`.
- **Atomicidad desde util_bbdd (G36, W-B2)**: la vista previa guarda `ParallelPlan.atomic` y `accept_non_atomic` se
  exige solo si es `False` (en las vistas previas anteriores a la 1.5.0, con más de un hilo). Sin esa aceptación la
  carga pide `ParallelOptions(require_atomic=True)`: util_bbdd garantiza un hilo y una transacción aunque su plan haya
  cambiado entre la vista previa y la carga (antes la web no lo controlaba).
- **Progreso por lote y cancelación entre lotes (G1, W-B3)**: `on_progress`/`cancel_token` con el puente `RunProgress`
  (fase `rows`, ADR-002). La decisión «en curso no se cancela» **cambia**: una carga en curso se puede cancelar, con
  confirmación en la UI. util_bbdd para antes del siguiente lote y deshace la transacción en curso: sin plan paralelo
  eso es **toda la carga** (no queda nada); con plan paralelo, las particiones terminadas quedan confirmadas
  (`committed`). `result.json` lleva `cancelled` y el run termina `cancelled`. El worker no termina nunca el subproceso
  de un `bulk_apply` por una cancelación (`CANCEL_BETWEEN_STEPS_ONLY`); el `job_timeout` sí. Con esto ninguna escritura
  queda «no cancelable en curso» (`NOT_CANCELLABLE_RUNNING` retirado).

## Enmienda (2026-10-30): ids propios en la carga

- **Columnas identity (`override_identity`)**: un insert en PostgreSQL con columnas `GENERATED ALWAYS AS IDENTITY` en
  el fichero se puede cargar con sus valores (`bulk_insert_from_df(override_identity=True)`, `OVERRIDING SYSTEM
  VALUE`). Sin la opción, la validación de la web lo da como error (util_bbdd lo rechaza también en el modo seco) y
  ofrece la salida: activarla o poner esas columnas en «(no cargar)». SQL Server no lo necesita (util_bbdd pone
  `IDENTITY_INSERT`); en el resto de motores no aplica.
- **Ajuste del contador de la PK (`sync_pk_sequences`)**: tras un insert terminado (sin error ni cancelación) la web
  llama a `BulkCrud.sync_pk_sequences([tabla])`, activado por defecto como «Ajustar secuencias de PK» del volcado
  (D-1). Escribe en el destino (`setval`, `DBCC CHECKIDENT`, `AUTO_INCREMENT`, `ALTER SEQUENCE`) dentro del mismo
  flujo protegido de esta ADR; sus errores no hacen fallar la carga: quedan en `result.json` (`pk_sync`) y en el
  mensaje final.
- **Ids asignados por la BD (`exclude_autoincrement_pk`)**: con la opción, util_bbdd quita del INSERT las columnas de
  PK autoincrementales (`is_identity_pk`: `autoincrement is True` o con `identity`), aunque vengan en el fichero; es
  incompatible con `override_identity`. La web replica ese criterio (la función es privada) para avisar: la vista
  previa devuelve `autoincrement_pk` y el formulario marca la PK en el mapeo con el catálogo del explorador. Con la PK
  excluida no se cuentan coincidencias. SQLite refleja la PK con `autoincrement="auto"`: util_bbdd no la excluye y la
  vista previa lo avisa. Poner la PK en «(no cargar)» sigue siendo equivalente.

## Enmienda (2026-10-30): ficheros grandes

Para cargar CSV de hasta 1 GB sin tenerlos enteros en memoria:

- **Lectura por bloques** (`domain/uploads/files.py`, `iter_frames`): `pandas.read_csv(chunksize=50 000)`. La
  codificación se comprueba decodificando el fichero por bloques; antes se leía y decodificaba entero (varias veces su
  tamaño en memoria) incluso para describir 5 filas. Un Excel sigue leyéndose entero.
- **Vista previa**: el mapeo se valida con el primer bloque; las filas y las coincidencias por PK se cuentan
  recorriendo el fichero (claves deduplicadas por bloque, no entre bloques). El SQL del modo seco se genera solo con
  las **primeras 1 000 filas** (`sql_sample_rows` en la vista previa y una cabecera en `carga_<op>.sql`): con
  millones de filas el SQL completo era inmanejable.
- **Carga**: sin plan paralelo, `bulk_insert|update|delete_from_chunks` de util_bbdd (5.2.0). Consume los bloques de
  forma perezosa en una sola `bulk_session` (atómica), con `on_progress`/`cancel_token` y con los rechazos de
  `on_error="isolate"` (`RejectOptions`), igual que `*_from_df`. util_bbdd no conoce el total (`total=None`): el
  progreso usa las filas contadas en la vista previa (mismo fichero, SHA-256). Con plan paralelo (`*_from_chunks` no
  reparte en hilos), los bloques se juntan en un `DataFrame` y se usa `*_from_df`; la vista previa avisa
  (`memory_warning`) si el fichero pasa de 200 MB.
- **Subida**: el multipart se recibe en `TMPDIR` del volumen workspace (el *entrypoint* lo crea) en vez del `tmpfs`
  `/tmp`, y la pantalla lo envía con `XMLHttpRequest` para mostrar el progreso y poder cancelarlo.

Sin huecos nuevos en util_bbdd. Pendiente: la subida por partes reanudable, si la subida HTTP de 1 GB falla en redes
inestables.
