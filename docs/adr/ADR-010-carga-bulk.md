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
