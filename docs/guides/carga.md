# Carga bulk desde fichero

Guía de uso de la carga bulk (desde la 0.10.0, Fase 9; vigente en 1.0.0). **Inserta, actualiza o borra** filas de una tabla a partir de un fichero
CSV o Excel, con `BulkCrud` de util_bbdd. La tabla destino debe existir. Diseño de seguridad:
[ADR-010](../adr/ADR-010-carga-bulk.md).

## 1. Subir el fichero

En el proyecto, pestaña **Carga** (rol editor) → *Ficheros*: elige un `.csv` o `.xlsx` y **Subir**.

- Tamaño máximo por fichero: 50 MB (`UBW_UPLOAD_MAX_MB`); el Excel, como mucho 300 MB descomprimido. Cuentan para la
  cuota del propietario del proyecto.
- Se comprueba el **contenido real**: un `.xlsx` con macros, un fichero binario con extensión `.csv` o un zip que no
  es Excel se rechazan.
- Los ficheros se borran a los **7 días** (`UBW_UPLOAD_RETENTION_DAYS`) salvo que una carga los use. Contienen datos
  de negocio: los ven los miembros del proyecto.

## 2. Vista previa (modo seco)

En *Nueva carga*:

| Campo | Efecto |
|---|---|
| Fichero, operación | **Insertar**, **Actualizar** (por clave primaria) o **Borrar** (por clave primaria) |
| Conexión, schema y tabla destino | Dónde se escribe. Al elegir la conexión se ofrecen sus schemas (sin los del sistema) y las tablas del schema elegido o, vacío, del de la conexión; también se pueden escribir. Si el catálogo no se puede leer (p. ej. conexión privada de otro miembro), se escriben a mano |
| Hoja / separador y codificación | Excel: hoja (la primera por defecto). CSV: el separador se detecta entre coma, punto y coma, tabulador y barra vertical (coma si no se reconoce) y la codificación probando UTF-8, Windows-1252 y Latin-1; se pueden fijar si las columnas salen juntas o hay caracteres raros (habitual: CSV de Excel en español, con `;`) |
| Columnas | Columna de la tabla para cada columna del fichero, o «no cargar». Si se puede leer la tabla, se ofrecen sus columnas y se propone la del mismo nombre |
| Apartar filas | Las que el destino no admita van a `rechazos.csv` en vez de hacer fallar la carga |
| Plan paralelo | util_bbdd reparte las filas en hilos si compensa; con más de un hilo **deja de ser atómica** |

**Vista previa** lanza una ejecución que no escribe nada. Su detalle muestra las filas del fichero y de la tabla, las
**filas afectadas** (las que ya existen por clave primaria: en insert, posibles duplicados), las primeras filas tal
como se cargarán, las columnas ignoradas, el plan paralelo y el **SQL** que se ejecutaría (completo en Artefactos).

Errores que impiden cargar: columnas que no existen en la tabla, columnas obligatorias sin valor en un insert, tabla
sin clave primaria o fichero sin ella en update/delete, o un update sin columnas además de la clave.

## 3. Cargar

Requisitos (si falta alguno, el panel *Ejecutar la carga* explica cuál): permiso **«Puede escribir datos»** (lo
concede un administrador en *Usuarios*), ser **propietario** del proyecto, conexión destino **no** de solo lectura,
vista previa **sin errores** y de **menos de 60 minutos**.

La confirmación pide marcar que has revisado la vista previa y escribir el alias del destino; en **actualizar y
borrar**, también el **número de filas afectadas**; si el plan no es atómico (más de un hilo), aceptarlo. Si no
lo aceptas, util_bbdd carga en un solo hilo y en una sola transacción aunque el plan cambie al ejecutar.

La carga usa el fichero y los parámetros de la vista previa. Antes de escribir comprueba de nuevo el fichero, la
conexión, la estructura de la tabla y, en actualizar y borrar, que las filas afectadas sigan siendo las confirmadas:
si algo cambió, falla con `preview_changed` sin tocar nada. No se puede cargar mientras haya otra escritura
(migración, volcado o carga) sobre el mismo destino.

Mientras carga, el detalle muestra las filas enviadas («Filas: 5000 de 20000 (clientes)»).

> Una carga **en curso se puede cancelar** (con confirmación): para **entre lotes**. Sin plan paralelo va en una sola
> transacción y **se deshace entera**: no queda nada en el destino. Con plan paralelo, las particiones ya terminadas
> quedan confirmadas y el resultado dice cuántas filas. Si se agota el tiempo máximo (`UBW_JOB_TIMEOUT_SECONDS`), el
> proceso se termina a mitad: la transacción en curso la deshace el motor.

## 4. Resultado

Filas del fichero, **filas confirmadas** (las que util_bbdd envió y confirmó: incluyen las apartadas y, al actualizar
o borrar, las claves que no existían), filas de la tabla antes y después, filas apartadas, el error (solo la primera
línea del motor, sin valores) y, si fue paralela, cada partición. El recuento de la tabla antes y después sirve de
comprobación: si no cuadra con las filas confirmadas (otro proceso escribió a la vez, un disparador…), el resultado lo
avisa. Sin filas apartadas ni errores, al insertar la tabla crece en las filas confirmadas, al borrar decrece en las
filas que coincidían y al actualizar no cambia. Artefactos: `result.json`, la auditoría de util_bbdd `carga.jsonl` y, si
se apartaron filas, `rechazos.csv` (datos de negocio).

## Errores frecuentes

| Código | Causa | Qué hacer |
|---|---|---|
| 413 al subir | Fichero mayor que el límite (o el proxy lo corta antes) | Divide el fichero; en el proxy, `client_max_body_size` |
| 415 / 422 al subir | Extensión no admitida, contenido que no corresponde o Excel con macros | Guarda como `.csv` o `.xlsx` sin macros |
| `invalid_file` | No se pudo leer (codificación, separador, hoja) o supera `UBW_BULK_MAX_ROWS` | Fija separador y codificación, o divide el fichero |
| 403 al cargar | Sin «Puede escribir datos» o sin ser propietario | Pídelo a un administrador o al propietario |
| 409 al cargar | La vista previa tiene errores u otra escritura en curso sobre el destino | Corrige y repite la vista previa, o espera |
| 422 «número de filas» | `confirm_rows` distinto de las filas afectadas | Escribe el número que muestra la vista previa |
| `preview_changed` | Cambiaron la tabla, el mapeo o las filas afectadas | Repite la vista previa |
| `bulk_failed` | El motor rechazó la operación (todo o nada sin paralelo) | Lee el error; prueba con «Apartar filas» |
| `bulk_partial` | Falló alguna partición de una carga paralela; las demás quedaron | Revisa las particiones y corrige el destino |
