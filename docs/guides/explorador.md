# Explorador de metadatos, queries nombradas y SQL

Guía de uso del explorador. Disponible desde la versión 0.5.0 (Fase 4); vigente en 1.0.0.

## Explorar una conexión

En el detalle de una conexión, **Explorar** abre el explorador. Puede usarlo cualquiera que vea la conexión
(propia o compartida): solo lee el catálogo.

- **Schema**: por defecto, el de la conexión. Los del sistema (`information_schema`, `pg_catalog`, `SYS`…) se ocultan;
  *Mostrar schemas del sistema* los incluye.
- **Árbol**: tablas, vistas y rutinas del schema, con un filtro por nombre.
- **Caché**: la primera lectura de un schema puede tardar (hasta 2 minutos en schemas muy grandes); después se
  guarda y se muestra la fecha de lectura. **Refrescar** vuelve a leer el catálogo. Editar la conexión borra su
  caché.

Al elegir una **tabla** se ven sus pestañas:

| Pestaña | Contenido |
|---|---|
| Columnas | Orden, nombre, tipo, nulos, valor por defecto, comentario; `PK` e identidad marcadas |
| Claves | Clave primaria, únicas y checks |
| Índices | Nombre, columnas y si es único |
| Relaciones | Claves foráneas que salen de la tabla y las que llegan a ella (pulsa la tabla para abrirla) |
| DDL | `CREATE TABLE` que devuelve el motor (o la reconstrucción en MySQL/MariaDB, sin índices ni FK) |

Las **vistas** y **rutinas** muestran su DDL. Si el motor no lo devuelve (permisos, objetos cifrados), se indica.

## Queries nombradas

Pestaña *Queries nombradas* del explorador: consultas preparadas por un administrador para el motor de la
conexión. Elige una, rellena sus parámetros y pulsa **Ejecutar**.

- Los parámetros **solo admiten identificadores** (letras, números, `_`, `$`, `#`) **o números**: no se pueden
  escribir textos con espacios, comillas ni operadores. Es la protección frente a inyección SQL, porque util_bbdd
  sustituye los parámetros en el texto de la consulta.
- *Máx. filas* limita el resultado (por defecto y como máximo, 1000). Si hay más filas, se avisa de que el resultado
  está recortado.

### Para administradores: crear queries

*Administración → Queries nombradas → Nueva query*:

- **Motor** (no se puede cambiar después), **nombre** (letras, números, `.`, `-`, `_`) y descripción.
- **Plantilla SQL**: una única consulta de lectura (`SELECT`, `WITH`, `UNION`). Los parámetros se escriben
  `{nombre}`, igual que en util_bbdd. Se rechazan las plantillas que no sean de lectura.

Ejemplo (PostgreSQL):

```sql
SELECT relname AS tabla, n_live_tup AS filas
FROM pg_stat_user_tables
WHERE schemaname = '{schema}'
ORDER BY n_live_tup DESC
```

## SQL libre

Pestaña **SQL** de un proyecto. Requisitos, todos a la vez:

1. Ser **editor o propietario** del proyecto.
2. Tener el permiso **«Puede ejecutar SQL libre»**, que activa un administrador en *Usuarios*.
3. Usar una conexión del proyecto marcada como **Solo lectura**.

Solo se admite **una consulta de lectura** (`SELECT`, `WITH … SELECT`, `UNION`). Se rechazan `INSERT`, `UPDATE`,
`DELETE`, `CREATE`, `DROP`, `SELECT … INTO`, `FOR UPDATE`, `EXEC`, varias sentencias separadas por `;`, etc.
Además, la consulta se ejecuta dentro de una **transacción de solo lectura** del motor y siempre se deshace al
terminar. Ctrl+Enter ejecuta.

- Si la consulta falla, se muestra el mensaje del motor (recortado), para poder corregirla.
- Tiempo máximo: 30 s; filas: hasta 1000 (configurable por el administrador del servidor).
- Todas las ejecuciones quedan en la **auditoría** con el texto de la consulta.

> **SQL Server** no tiene transacciones de solo lectura: la protección depende del análisis de la consulta. La
> pantalla lo avisa. En cualquier motor, lo más seguro es que la conexión use un **usuario de BD con solo permisos
> `SELECT`**.

HSQLDB no admite SQL libre.
