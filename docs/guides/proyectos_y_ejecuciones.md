# Proyectos y ejecuciones

Guía de uso de los proyectos y del motor de ejecuciones. Disponible desde la versión 0.4.0 (Fase 3); vigente en 1.0.0.

## Proyectos

*Proyectos → Nuevo proyecto* crea un proyecto del que eres **propietario**. Solo ves los proyectos de los que eres
miembro; los administradores de la aplicación tampoco ven los ajenos.

| Rol | Puede |
|---|---|
| Lector (`viewer`) | Ver el proyecto, sus miembros, conexiones, ejecuciones y artefactos; descargar |
| Editor (`editor`) | Lo anterior y lanzar, cancelar, relanzar y purgar ejecuciones; asociar o quitar conexiones |
| Propietario (`owner`) | Todo, además de editar o borrar el proyecto y gestionar los miembros |

- **Miembros** (pestaña *Miembros*): el propietario añade usuarios por su nombre de usuario y cambia su rol. Siempre
  debe quedar al menos un propietario. Cualquier miembro puede *Salir del proyecto*.
- **Conexiones** (pestaña *Conexiones*): un editor asocia una conexión **propia o compartida** con un **alias**
  (`origen`, `destino`…). Las ejecuciones usan el alias; los demás miembros pueden usar la conexión **sin ver su
  contraseña**. Asociar una conexión privada tuya es, por tanto, permitir que el proyecto la use.
- **Plantillas** (pestaña *Plantillas*): plantillas Word y Excel para la documentación; las suben los editores y
  se ven también las globales ([Plantillas Word y Excel](documentacion.md#plantillas-word-y-excel)).
- **Borrar** (pestaña *Ajustes*): elimina el proyecto con todas sus ejecuciones y ficheros. No se puede borrar con
  ejecuciones en cola o en curso.

## Lanzar una ejecución

En la pestaña *Ejecuciones*, **Lanzar ejecución** (editores) abre el formulario de la operación elegida, generado a
partir de sus parámetros. Operaciones disponibles:

- **Documentación de la base de datos** y **Grafo de relaciones**: ver [Documentación y grafos](documentacion.md).
- **Comparación de esquemas**: ver [Comparación de esquemas](comparacion.md).
- **Plan de migración DDL** (y su aplicación desde el plan): ver [Migración DDL](migracion.md).
- **Volcado de datos: vista previa** (y el volcado desde ella): ver [Volcado de datos](volcado.md).
- La **carga bulk** desde un fichero se lanza desde la pestaña *Carga* del proyecto: ver
  [Carga bulk desde fichero](carga.md).
- **Prueba del motor de ejecuciones** (`noop`), pensada para validar la instalación:

| Parámetro | Efecto |
|---|---|
| Pasos / Segundos por paso | Duración simulada; el progreso avanza por pasos |
| Fallar a propósito | Termina en error (prueba de fallos) |
| Conexión a probar | Alias de una conexión del proyecto que se prueba desde el worker (respeta los destinos permitidos) |

La ejecución queda **En cola** hasta que el *worker* la toma.

Límites (configurables por el administrador del servidor): como máximo **5 ejecuciones en cola o en curso** por
usuario y una **cuota de 1 GB** de ficheros. Si se supera la cuota, purga ejecuciones antiguas.

## Seguir el progreso

El detalle de la ejecución se actualiza **en vivo**: estado, fase (*Preparando*, *Conectando*, *Ejecutando*,
*Generando informes*), mensaje y barra de progreso. Si la conexión en vivo falla (por ejemplo, tras un proxy que la
almacena), la página se actualiza cada 2 segundos.

| Estado | Significado |
|---|---|
| En cola | Esperando al worker |
| En curso | Ejecutándose en un proceso aislado |
| Correcta / Fallida | Terminó; si falló, se muestra el motivo |
| Cancelada | Un usuario la canceló |
| Purgada | Sus ficheros se borraron (a mano o por retención); se conserva el resumen |

**Cancelar** (editores): una ejecución en cola se cancela al momento; una en curso se detiene en unos segundos
(el worker termina su proceso).

## Historial y artefactos

- El historial del proyecto muestra **una fila por ejecución** (operación, usuario, estado, fecha, duración y número
  de artefactos), con filtro por estado y búsqueda por id, operación o usuario. *Ejecuciones* en el menú lista las de
  todos tus proyectos.
- En el detalle, el **navegador de artefactos** agrupa los ficheros por tipo. HTML, SVG y PNG se ven en un marco aislado
  (sin scripts); Markdown se muestra con formato (también aislado); SQL, el log y `run.json` como texto. Los
  ficheros del sitio HTML de una documentación no se listan: el sitio se abre en su tarjeta. Cada fichero se puede **descargar**, y
  **Descargar ZIP** baja la ejecución completa.
- **Relanzar** crea una ejecución nueva con los mismos parámetros (indica de cuál procede).
- **Purgar** borra los ficheros de una ejecución terminada para liberar cuota; el resumen queda en el historial.

Cada ejecución guarda en su carpeta un manifiesto `run.json` (operación, parámetros, conexiones por alias,
versiones, tiempos, estado y artefactos con SHA-256) y un `run.log`. Ninguno contiene contraseñas.

## Retención

El servidor purga automáticamente las ejecuciones terminadas con más de **30 días** y conserva como máximo las
**100 más recientes** de cada proyecto (valores configurables, ver [arquitectura](../architecture.md#configuración)).
