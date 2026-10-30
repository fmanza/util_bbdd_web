# Volcado de datos

Guía de uso del volcado de datos (desde la 0.9.0, Fase 8; vigente en 1.0.0). Copia **filas** de una conexión del proyecto a otra con `DumpOrchestrator`
de util_bbdd: mismo motor o distinto. Las **tablas destino deben existir** (créalas antes, p. ej. con la
[migración DDL](migracion.md)). Diseño de seguridad: [ADR-009](../adr/ADR-009-volcado-de-datos.md).

## 1. Vista previa (modo seco)

En *Ejecuciones*, **Lanzar ejecución → Volcado de datos: vista previa** (rol editor). No escribe nada.

| Campo | Efecto |
|---|---|
| Conexión y schema origen / destino | De dónde se leen y dónde se escriben las filas |
| Tablas | Separadas por comas (sin distinguir mayúsculas); vacío = todas las del origen |
| Carga | **Vaciar el destino antes de cargar** (desactivado: las filas se **añaden**) y ajustar secuencias de PK |
| Errores | Filas que el destino no admite: **fallar la tabla** o **apartarlas** a `rechazos.csv`, con un máximo por tabla |
| Rendimiento | Filas por lote, tablas en paralelo (1–4) e índices secundarios |

El detalle muestra el **orden de carga** por claves foráneas (las tablas en ciclos van al final), las filas en origen y
destino y, por tabla, columnas que no se copian, columnas obligatorias del destino que el origen no tiene y FK a tablas
fuera del volcado. Avisos:

- tablas que **no existen** en el destino (no se cargan);
- destino **con filas** sin vaciar (se añaden; pueden duplicarse claves);
- **ciclos** de FK;
- motor sin gestión de constraints (SQLite: se cargan con las constraints activas).

«Apartar» funciona igual en todos los motores (también con destino Oracle) y, con origen SQLite, las fechas guardadas
como texto ISO se cargan como fechas.

## 2. Volcar

Requisitos (si falta alguno, el panel *Volcar los datos* explica cuál): permiso **«Puede escribir datos»** (lo concede un
administrador en *Usuarios*), ser **propietario** del proyecto, conexión destino **no** de solo lectura y vista previa
de **menos de 60 minutos**.

**Volcar en «destino»…** abre la confirmación: marca que has revisado la vista previa y escribe el alias del destino.
Si la vista previa **vacía el destino**, el botón es *Vaciar y volcar*, se indica cuántas filas se borrarán y hay que
escribir también **VACIAR**.

El volcado usa exactamente los parámetros de la vista previa. Antes de escribir vuelve a analizar las tablas: si la
estructura cambió (tablas, columnas u orden) o algún alias apunta ya a otra conexión, falla con `preview_changed`
sin tocar nada. No se puede volcar mientras haya una migración o un volcado en curso sobre el mismo destino.

Mientras carga, el detalle muestra las tablas terminadas y las filas escritas de la tabla en curso.

> **Destino MariaDB o MySQL**: util_bbdd usa por defecto `read_timeout = 30` y `write_timeout = 60` (segundos de
> espera del cliente por sentencia). Durante el volcado, las consultas al catálogo pueden esperar a los bloqueos del
> vaciado y de los índices secundarios, y pasar de 30 s corta la conexión: falla con
> `util_bbdd falló (InterfaceError)` y `Lost connection to server during query` en `volcado.jsonl`. Sube los dos
> parámetros en la conexión destino (p. ej. `600`) antes de volcar.

> Un volcado **en curso se puede cancelar** (con confirmación): para **entre lotes**, deshace la tabla en curso,
> reactiva las constraints y termina como *cancelado*. Las tablas ya terminadas **quedan cargadas** en el destino; el
> resultado las lista y el detalle por tabla está en `volcado.jsonl`. Si se agota el tiempo máximo
> (`UBW_JOB_TIMEOUT_SECONDS`), el proceso se termina a mitad: ver [Constraints sin restaurar](#constraints-sin-restaurar).

## 3. Resultado

El detalle del volcado muestra, por tabla, estado, filas en origen y en destino antes y después, filas apartadas y el
error (solo la primera línea del motor, sin los valores de las filas que lo provocaron). También las
**constraints que no se reactivaron** (p. ej. filas huérfanas). Artefactos: el **informe Excel** de util_bbdd, `rechazos.csv` (si se apartaron filas: contiene
datos de negocio) y el rastro de auditoría `volcado.jsonl`.

### Constraints sin restaurar

Con destino SQL Server, PostgreSQL u Oracle, util_bbdd anota qué desactiva antes de cargar. Si el proceso del volcado
muere (se agota el tiempo máximo, se reinicia el worker) o alguna constraint no se puede reactivar, el resultado
muestra **Constraints sin restaurar** con las tablas o constraints afectadas: el destino no comprueba sus claves
foráneas hasta restaurarlas. Mientras tanto no se puede volcar otra vez en ese destino ni purgar ese volcado (la
retención tampoco lo purga).

- Si el proceso murió, el worker lanza **solo** una restauración (`dump_restore`) con los mismos controles que el
  volcado.
- Si no, o si esa restauración falla, el propietario con «Puede escribir datos» pulsa **Restaurar constraints…** y
  escribe el alias del destino. Una constraint que no se puede reactivar (filas que no la cumplen) sigue pendiente:
  corrige los datos y vuelve a restaurar.

En MySQL/MariaDB las constraints se desactivan solo en la sesión del volcado y vuelven solas al cerrarse; SQLite no
las toca.

## Errores frecuentes

| Código | Causa | Qué hacer |
|---|---|---|
| 403 al volcar | Sin «Puede escribir datos» o sin ser propietario | Pídelo a un administrador o al propietario |
| 422 «más de 60 minutos» | Vista previa antigua | Lanza otra vista previa |
| `preview_changed` | Cambiaron tablas o columnas desde la vista previa | Repite la vista previa y revísala |
| `dump_partial` | Alguna tabla falló o alguna constraint no se reactivó | Revisa el resultado por tabla; corrige los datos o el destino |
| 409 «constraints sin restaurar» | Un volcado anterior sobre ese destino las dejó desactivadas | Restáuralas desde el resultado de ese volcado |
| `restore_partial` | Alguna constraint no se pudo reactivar al restaurar | Corrige las filas que no la cumplen y vuelve a restaurar |
| `invalid_params` | Tabla o schema inexistente en el origen | Revisa los nombres en el explorador |
