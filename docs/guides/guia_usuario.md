# Guía de usuario

Visión de conjunto de util_bbdd_web 1.0.0: qué se puede hacer, quién puede hacerlo y en qué orden. Cada apartado
enlaza con su guía detallada.

## 1. Para qué sirve

util_bbdd_web pone en el navegador las operaciones de la librería util_bbdd sobre bases de datos MariaDB, MySQL,
Oracle, PostgreSQL, SQLite, SQL Server y HSQLDB:

| Quieres… | Operación | Guía |
|---|---|---|
| Ver tablas, columnas, índices y DDL; consultar | Explorador, queries nombradas y SQL de solo lectura | [Explorador y SQL](explorador.md) |
| Documentar una base de datos (Word, Excel, HTML) | Documentación de la base de datos | [Documentación y grafos](documentacion.md) |
| Dibujar las relaciones entre tablas | Grafo de relaciones | [Documentación y grafos](documentacion.md) |
| Saber qué cambió entre dos esquemas | Comparación de esquemas | [Comparación](comparacion.md) |
| Llevar la estructura a otro motor | Plan de migración DDL (y aplicarlo) | [Migración DDL](migracion.md) |
| Copiar filas de una BD a otra | Volcado de datos (vista previa y volcado) | [Volcado](volcado.md) |
| Insertar, actualizar o borrar filas desde un CSV/Excel | Carga bulk (vista previa y carga) | [Carga bulk](carga.md) |

Todo lo que tarda (documentar, comparar, migrar, volcar, cargar) se lanza como **ejecución**. Una ejecución corre en
segundo plano, muestra su progreso en vivo y guarda sus resultados en su propia carpeta, que se descarga como
artefactos o en un ZIP.

## 2. Conceptos

| Concepto | Qué es |
|---|---|
| **Motor** | Tipo de base de datos con sus capacidades (*Motores*) |
| **Conexión** | Datos para conectar con una BD concreta. La contraseña se guarda cifrada. Puede ser **personal** o **compartida**, y marcarse **«Solo lectura»** |
| **Proyecto** | Espacio de trabajo con miembros, conexiones asociadas por **alias** e historial de ejecuciones |
| **Ejecución** | Una operación lanzada en un proyecto: estado, progreso, registro y artefactos |
| **Artefacto** | Fichero que produce una ejecución: informe, SQL, imagen, sitio HTML, rechazos… |

## 3. Quién puede hacer qué

**Rol en la aplicación**:

- `user`: trabaja en sus proyectos.
- `admin`: además gestiona usuarios, sesiones, destinos permitidos, queries nombradas y auditoría.

**Rol en cada proyecto**:

| Puede… | Lector | Editor | Propietario |
|---|:-:|:-:|:-:|
| Ver el proyecto, su historial y descargar artefactos | ✓ | ✓ | ✓ |
| Lanzar, cancelar y relanzar ejecuciones; pestañas *SQL* y *Carga* | | ✓ | ✓ |
| Asociar conexiones | | ✓ | ✓ |
| Gestionar miembros, ajustes y borrar el proyecto | | | ✓ |
| Escribir en una BD destino (aplicar migración, volcar, cargar) | | | ✓ + permiso especial |

**Permisos especiales**: los concede un administrador al editar el usuario.

| Permiso | Para | Además exige |
|---|---|---|
| *Puede ejecutar SQL libre* | Consultas de lectura en la pestaña *SQL* | Ser editor; la conexión debe ser «Solo lectura» |
| *Puede aplicar DDL* | Crear en el destino lo que genera un plan de migración | Ser propietario; un modo seco reciente; escribir el alias del destino |
| *Puede escribir datos* | Volcados y cargas bulk | Ser propietario; una vista previa reciente; escribir el alias (y más confirmaciones si borra o vacía) |

Ninguna operación escribe en una conexión marcada como «Solo lectura».

## 4. Primeros pasos

1. **Inicia sesión** con la cuenta que te dio el administrador y cámbiala en el menú con tu nombre → *Cambiar
   contraseña*. Requisitos: al menos 12 caracteres, que no sea una contraseña común ni tu nombre de usuario
   ([Usuarios y sesiones](usuarios_y_sesiones.md)).
2. **Crea una conexión** en *Conexiones → Nueva conexión*: elige el motor y rellena sus parámetros. Pulsa
   **Probar conexión** para comprobarla. Si el destino no está en la lista de *Destinos permitidos*, pídeselo a un
   administrador ([Motores y conexiones](conexiones.md)).
3. **Explora** la conexión (*Conexiones → Explorar*) para ver schemas, tablas y su DDL.
4. **Crea un proyecto** en *Proyectos → Nuevo proyecto*. En su pestaña *Conexiones*, asocia las conexiones con un
   alias (`origen`, `destino`…) y, en *Miembros*, añade compañeros con su rol.
5. **Lanza una ejecución** en *Ejecuciones → Lanzar ejecución*. Elige la operación, rellena el formulario y sigue
   el progreso en el detalle ([Proyectos y ejecuciones](proyectos_y_ejecuciones.md)).
6. **Revisa los resultados** en el detalle de la ejecución. Según la operación, hay un visor (diff, plan de
   migración, vista previa de volcado o carga, sitio HTML) y los artefactos para descargar.

## 5. Escribir en una base de datos

Aplicar una migración, volcar datos o cargar un fichero siempre se hace en **dos pasos**:

1. **Vista previa o modo seco**: un editor la lanza y no escribe nada. Muestra qué se hará, avisos y filas
   afectadas, y el SQL cuando corresponde.
2. **Escritura**: desde esa vista previa, el **propietario** con el permiso correspondiente pulsa el botón de
   aplicar. Antes confirma que la ha revisado, escribe el alias del destino y, según el caso, «VACIAR» o el número
   de filas afectadas.

La escritura usa exactamente lo revisado. Falla sin tocar nada si la vista previa tiene más de 60 minutos o si algo
cambió desde entonces: la estructura, la conexión, el fichero o las filas afectadas. Una escritura en curso no se
cancela, y solo puede haber una a la vez por destino.

## 6. Si algo falla

- Los errores muestran un título, una explicación y una **Referencia**. Facilítala al administrador: con ella
  encuentra la petición en los registros.
- «Demasiadas peticiones»: espera los segundos que indica.
- «Credenciales no válidas»: tras 5 fallos seguidos, la cuenta se bloquea 15 minutos. Un administrador puede
  desbloquearla restableciendo la contraseña.
- Más casos: [Solución de problemas](troubleshooting.md).

## 7. Para administradores

- Puesta en marcha y operación: [Puesta en marcha](puesta_en_marcha.md) y [Despliegue](deployment.md).
- *Administración*:
  - **Usuarios**: altas, roles, permisos especiales, desactivar y restablecer contraseña.
  - **Sesiones**: ver y cerrar sesiones activas.
  - **Destinos permitidos**: hosts y redes a los que se puede conectar.
  - **Queries nombradas**: consultas reutilizables del explorador.
  - **Auditoría**: inicios de sesión, cambios y escrituras.

  Detalle en [Usuarios y sesiones](usuarios_y_sesiones.md) y [Explorador y SQL](explorador.md).
