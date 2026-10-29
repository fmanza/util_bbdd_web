# Motores y conexiones

Guía de uso del catálogo de motores y de las conexiones. Disponible desde la versión 0.3.0 (Fase 2); vigente en 1.0.0.

## Catálogo de motores

*Motores* muestra los motores que soporta util_bbdd (MariaDB, MySQL, Oracle, PostgreSQL, HSQLDB, SQL Server y
SQLite) en una matriz:

| Columna | Significado |
|---|---|
| Versiones / Puerto | Rango de versiones soportado y puerto por defecto |
| Drivers | En azul, instalados en el servidor; en gris («no instalado»), los que faltan en esta imagen |
| Async | El motor admite ejecución asíncrona en util_bbdd |
| Migración (origen / destino) | Puede usarse como origen o destino de la migración DDL (Fase 7) |
| Readiness | util_bbdd tiene comprobaciones de condiciones del motor |

Al pulsar un motor se abre su **ficha**: descripción, **operaciones que admite** (documentación, grafo, comparación,
migración, volcado y si gestiona las constraints, carga, readiness y async; la matriz es de util_bbdd), requisitos del
sistema, comando de instalación del driver, características y la tabla de **parámetros de conexión** (tipo, valor por defecto y descripción). *Nueva conexión con
este motor* abre el formulario ya con el motor elegido.

## Crear una conexión

*Conexiones → Nueva conexión*:

1. Elige el **motor**: el formulario se genera con sus parámetros.
2. Rellena el **nombre** (único entre tus conexiones) y los parámetros obligatorios (marcados con `*`). Los menos
   habituales están en *Opciones avanzadas*. Si dejas un campo vacío, se usa el valor por defecto de util_bbdd.
3. Escribe la **contraseña**: se guarda **cifrada** y **nunca se vuelve a mostrar**, ni siquiera a ti. Al editar,
   déjala vacía para conservar la guardada.
4. **Solo lectura** (activado por defecto): impide las operaciones que escriben en esa base de datos (migración
   aplicada, volcado, carga bulk) cuando se implementen.

Notas por motor:

- **SQLite**: `database` es la ruta del fichero **dentro de la carpeta de ficheros del servidor** (por ejemplo,
  `ventas.db`). El administrador copia ahí los ficheros ([despliegue](deployment.md#destinos-y-ficheros-de-las-conexiones)).
- **Oracle**: indica `dsn` (`host:puerto/servicio`) o bien `host`, `port` y `service_name` (o `sid`).
- **HSQLDB** necesita la imagen con Java (`WITH_HSQLDB=true`) y el JAR en la carpeta de ficheros.
- **SQL Server** usa `pymssql` por defecto; `pyodbc` requiere la imagen `WITH_ODBC=true`.
- Los certificados TLS (`ssl_ca`, `ssl_cert`, `ssl_key`) también deben estar en la carpeta de ficheros.
- `init_command` (MariaDB) no se admite: ejecutaría SQL arbitrario al conectar.

## Probar la conexión y readiness

En el detalle de una conexión:

- **Probar conexión** conecta (con un límite de 15 s) y muestra la versión del servidor y el tiempo. Si falla, el
  mensaje indica la causa sin datos internos:

  | Mensaje | Qué hacer |
  |---|---|
  | El destino no está en la lista de destinos permitidos | Pide a un administrador que añada el host o su red |
  | No se pudo conectar | Revisa host, puerto, usuario, contraseña y nombre de la BD |
  | La conexión no respondió a tiempo | Servidor inaccesible o cortafuegos |
  | El driver del motor no está instalado | Ver la ficha del motor; hace falta otra variante de la imagen |
  | Los parámetros de conexión no son válidos | Revisa la combinación de parámetros (p. ej. Oracle sin servicio) |

- **Readiness** ejecuta las comprobaciones de util_bbdd sobre el motor (configuración del servidor y de la conexión)
  y lista los hallazgos por nivel (`CRITICAL`, `WARNING`, `INFO`, `OK`) con su recomendación. Si no puede conectar,
  muestra solo las comprobaciones estáticas.

La lista de conexiones indica el resultado de la última prueba. Cambiar los parámetros o la contraseña lo borra.

## Conexiones compartidas

Un administrador puede crear conexiones **compartidas** (campo *Visibilidad*). Todos los usuarios las ven y pueden
probarlas, pero **no ven la contraseña** ni pueden editarlas o borrarlas: solo los administradores.

Las conexiones **privadas** solo las ve su propietario; ni siquiera los administradores ven las privadas de otros.

## Destinos permitidos (administradores)

*Administración → Destinos permitidos* controla a qué servidores pueden conectar las conexiones (protección
anti-SSRF). **Con la lista vacía, ninguna conexión de red funciona.**

| Patrón | Permite |
|---|---|
| `10.0.0.0/8` | Cualquier IP de esa red |
| `10.1.2.3` | Esa IP |
| `db.empresa.local` | Ese nombre de host |
| `*.empresa.local` | Cualquier subdominio (no `empresa.local` en sí) |
| `*` | Cualquier nombre de host (salvo los bloqueos siguientes) |

Siempre bloqueados: las IP de metadatos cloud (`169.254.0.0/16`), multicast y reservadas. **Loopback**
(`127.0.0.1`, `localhost`) solo se permite con una red explícita, por ejemplo `127.0.0.1/32`. Si un nombre resuelve
a varias IP, todas deben estar permitidas.

Todas las acciones (altas, ediciones, borrados, pruebas y cambios de la lista) quedan en *Auditoría*, sin
contraseñas.
