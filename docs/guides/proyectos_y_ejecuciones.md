# Proyectos y ejecuciones

Guía de uso de los proyectos y del motor de ejecuciones. Disponible desde la versión 0.4.0 (Fase 3); vigente en
1.21.0.

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
- **Plantillas** (pestaña *Plantillas*): plantillas Word y Excel y mapas de trazabilidad para la documentación; las
  suben los editores y se ven también las globales
  ([Plantillas Word y Excel](documentacion.md#plantillas-word-y-excel)).
- **Borrar** (pestaña *Ajustes*): elimina el proyecto con todas sus ejecuciones y ficheros. No se puede borrar con
  ejecuciones en cola o en curso.

## Lanzar una ejecución

En la pestaña *Ejecuciones*, **Lanzar ejecución** (editores) abre una ventana ancha (pantalla completa en el móvil):

- A la izquierda, la **lista de operaciones** agrupada por intención: *Documentar*, *Comparar*, *Mover a otra base de
  datos* y, al final, *Diagnóstico*. Al abrir se elige la documentación.
- A la derecha, el formulario de la operación en **tarjetas**: primero *Origen* (y *Destino*), después qué se genera
  y cómo. Las opciones que dependen de un interruptor solo aparecen con él activado (por ejemplo, el dialecto con el
  *Script SQL* o las opciones de cada formato de la documentación con ese formato marcado), y las que casi nunca se
  tocan van plegadas en **Opciones avanzadas**. Una tarjeta con errores se marca en rojo; si el error está en una
  opción plegada, la sección se abre sola.
- Abajo, siempre visible, un resumen de lo que hace la operación (por ejemplo, «Solo lee la conexión») con
  **Cancelar** y **Lanzar**.

Operaciones disponibles:

- **Documentación de la base de datos** y **Grafo de relaciones**: ver [Documentación y grafos](documentacion.md).
- **Comparación de esquemas**: ver [Comparación de esquemas](comparacion.md).
- **Plan de migración DDL** (y su aplicación desde el plan): ver [Migración DDL](migracion.md).
- **Volcado de datos: vista previa** (y el volcado desde ella): ver [Volcado de datos](volcado.md).
- La **carga bulk** desde un fichero se lanza desde la pestaña *Carga* del proyecto: ver
  [Carga bulk desde fichero](carga.md).
- **Prueba del motor de ejecuciones** (`noop`, en *Diagnóstico*), pensada para validar la instalación:

| Parámetro | Efecto |
|---|---|
| Pasos / Segundos por paso | Duración simulada; el progreso avanza por pasos |
| Fallar a propósito | Termina en error (prueba de fallos) |
| Conexión a probar | Alias de una conexión del proyecto que se prueba desde el worker (respeta los destinos permitidos) |

La ejecución queda **En cola** hasta que el *worker* la toma.

Límites: como máximo **5 ejecuciones en cola o en curso** por usuario (configurable por el administrador del
servidor) y una **cuota de 1 GB** por defecto para los ficheros de tus ejecuciones y de la carga, que un administrador
ajusta sin reiniciar, también por usuario ([Almacenamiento](usuarios_y_sesiones.md#almacenamiento)). Al llegar a la
cuota no puedes lanzar ejecuciones ni subir ficheros: purga ejecuciones antiguas (o se purgan solas, si el
administrador activó la purga por cuota). Tu uso está en *Mi espacio*.

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
(el worker termina su proceso). La **documentación**, el **grafo de todas las tablas** y la **comparación** paran por
sí mismos al terminar la tabla en curso, y su detalle muestra el avance («Word: 3 de 12», «Grafos: 5 de 40»,
«Tablas: 7 de 30 (pedidos)»); si no paran en un minuto, el worker termina su proceso. La comparación ya no para
mientras genera los informes, al final. **Aplicar una migración**, **volcar datos** y la **carga bulk** piden
confirmación y paran solo entre sentencias o entre lotes; el worker nunca termina su proceso por cancelar. Lo ya escrito
queda en el destino, salvo en una carga sin plan paralelo, que va en una sola transacción y se deshace entera.

## Historial y artefactos

- El historial del proyecto muestra **una fila por ejecución** (operación, usuario, estado, fecha, duración, tamaño y
  número de artefactos), con filtro por estado y búsqueda por id, operación, usuario o mensaje. *Ejecuciones* en el
  menú lista las de todos tus proyectos.
- En el detalle, el **navegador de artefactos** agrupa los ficheros por tipo. HTML, SVG y PNG se ven en un marco
  aislado (sin scripts); Markdown se muestra con formato (también aislado), con los colores y diagramas del tema
  elegido; el log y `run.json` como texto. Los scripts **SQL** se ven con resaltado (desde la 1.17.0; hasta 200 000
  caracteres, el resto en texto) y **Copiar SQL** los copia sin colores. Un fichero sin vista previa o demasiado
  grande para ella remite a descargarlo. Los ficheros del sitio HTML y de la documentación Markdown no se
  listan (se cuentan): se abren en su tarjeta ([Documentación y grafos](documentacion.md)). Cada fichero se puede
  **descargar**, y **Descargar ZIP** baja la ejecución completa.
- **Relanzar** crea una ejecución nueva con los mismos parámetros (indica de cuál procede). Las vistas previas de la
  carga y las escrituras (aplicar una migración, volcar, cargar, restaurar constraints) no tienen **Relanzar**: se
  lanzan de nuevo desde su origen.
- **Purgar** (editores) borra los ficheros de una ejecución terminada para liberar cuota; el resumen queda en el
  historial. Un volcado que dejó constraints sin restaurar en el destino no se purga hasta restaurarlas.
- **Eliminar** (solo administradores, desde *Administración → Todas las ejecuciones*) borra la ejecución por completo:
  ficheros y fila, que desaparece del historial. Si una ejecución se relanzó desde otra que ya no existe, «Relanzada
  de» muestra su id sin enlace y «(eliminada)».

Las listas de ejecuciones (*Ejecuciones* y la pestaña del proyecto) se ordenan pulsando la cabecera de una columna
(operación, usuario, estado, creada o tamaño), muestran **25 por página** y tienen búsqueda por id, operación, usuario
o mensaje. Lo mismo vale para el resto de listas de la aplicación (ver
[Usuarios y sesiones](usuarios_y_sesiones.md#listas)).

Cada ejecución guarda en su carpeta un manifiesto `run.json` (operación, parámetros, conexiones por alias,
versiones, tiempos, estado y artefactos con SHA-256) y un `run.log`. Ninguno contiene contraseñas.

## Retención

El servidor purga automáticamente las ejecuciones terminadas con más de **30 días** y conserva como máximo las
**100 más recientes** de cada proyecto (valores por defecto; un administrador los cambia sin reiniciar en
[Almacenamiento](usuarios_y_sesiones.md#almacenamiento)).
