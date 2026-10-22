# Comparación de esquemas

Guía de uso de la operación de la Fase 6 (versión 0.7.0). Se lanza desde la pestaña *Ejecuciones* de un proyecto
(rol editor) con dos conexiones del proyecto, o con la misma conexión y dos schemas distintos.

## Lanzar una comparación

**Comparación de esquemas** compara el **destino** con el **origen** usando `SchemaComparator` de util_bbdd.

| Sección | Opciones |
|---|---|
| (general) | Conexión y schema de **origen** (la referencia) y de **destino**; schema vacío = el de la conexión |
| Qué comparar | Tablas y columnas, índices, claves foráneas, comentarios, vistas y rutinas (las rutinas no se comparan en HSQLDB ni SQLite) |
| Informes | HTML, Excel, Word, Markdown y script SQL, y el dialecto del script (*Automático* = el del motor destino) |

**Schema**: se escribe como aparece en el explorador (en MySQL y MariaDB es la base de datos; en Oracle, el usuario
dueño de las tablas). No distingue mayúsculas si solo hay un schema con ese nombre. Si no existe, la ejecución falla
con «El schema «x» no existe en el origen/destino» en lugar de dar un diff vacío.

Se pueden comparar motores distintos (p. ej. PostgreSQL con MySQL); los tipos se comparan tal como los informa cada
motor, así que aparecerán diferencias de tipo esperables.

## Leer el diff

El detalle de la ejecución muestra **Diferencias de esquema**:

- Contadores de tablas *solo en origen*, *solo en destino* y *modificadas*, y el total de diferencias.
- Pestañas **Tablas**, **Vistas** y **Rutinas**, con filtro por nombre y por estado. Se muestran 100 objetos por
  pestaña; *Mostrar más* carga el resto.
- Cada tabla modificada se despliega con sus diferencias de columnas (tipo, nulos, clave primaria, valor por defecto,
  existencia), índices, claves foráneas y comentarios.
- Las vistas y rutinas muestran su definición en origen y destino **lado a lado**, con las líneas distintas
  resaltadas y marcadas con − / +.

| Estado | Significado |
|---|---|
| Solo en origen | Existe en el origen y falta en el destino |
| Solo en destino | Existe en el destino y no en el origen |
| Modificado | Existe en los dos con diferencias |

Si los esquemas son iguales en lo comparado, la ejecución termina **Correcta** con «Sin diferencias».

## Informes

La tarjeta **Informes de la comparación** tiene las descargas (Excel, Word, Markdown y SQL) y el **informe HTML**
navegable, aislado como el sitio de documentación ([ADR-007](../adr/ADR-007-sitio-html-aislado.md)). Sus diagramas
Mermaid se muestran como texto: util_bbdd los carga de Internet y la web no lo permite (GAPS G25).

> **El script SQL no se ejecuta.** Transforma el destino para igualarlo al origen e incluye `DROP` de lo que solo
> existe en el destino. Revísalo antes de aplicarlo a mano. Aplicar cambios desde la web llegará con la migración DDL.

Las etiquetas de origen y destino de los informes son `alias (motor) [schema]`: nunca llevan el servidor, el
usuario ni la ruta de los ficheros.

## Comparar con otra ejecución

En **Comparar con otra ejecución** elige una comparación anterior del mismo proyecto. La web muestra:

- **Nuevas**: diferencias que no estaban en la anterior.
- **Resueltas**: diferencias de la anterior que ya no aparecen.
- **Siguen**: diferencias presentes en las dos (con los valores actuales).

Una diferencia es la misma en las dos fechas si coinciden su tipo, la tabla, el objeto y el atributo (aunque cambien
los valores). Si las dos comparaciones no tienen el mismo origen y destino, se avisa: la evolución puede no tener
sentido.

## Errores frecuentes

| Código | Causa | Qué hacer |
|---|---|---|
| `invalid_params` | El schema no existe en ese lado | Revisa el nombre en el explorador |
| `connection_failed` | El origen o el destino no responde (el mensaje dice cuál) | Prueba la conexión desde su ficha |
| 413 en el visor | El diff supera 20 MB | Usa los informes descargables |
