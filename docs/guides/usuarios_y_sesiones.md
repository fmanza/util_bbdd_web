# Usuarios, sesiones y auditoría

Guía de uso de la identidad multiusuario. Disponible desde la versión 0.2.0 (Fase 1); vigente en 1.21.0.

## Roles

| Rol | Puede |
|---|---|
| `user` | Iniciar y cerrar sesión, cambiar su contraseña, elegir su tema y usar las secciones de la aplicación |
| `admin` | Lo anterior y, además, gestionar usuarios, ver y revocar sesiones, consultar la auditoría y el resto de *Administración* (destinos permitidos, plantillas, queries nombradas, ejecuciones de todos los proyectos y almacenamiento) |

El primer administrador se crea por línea de comandos ([despliegue](deployment.md#primer-administrador)); no existen
credenciales por defecto.

## Iniciar y cerrar sesión

- Entra en la aplicación: sin sesión se abre la pantalla **Iniciar sesión**. Tras entrar vuelves a la página que
  habías pedido.
- El usuario no distingue mayúsculas (`Ana` y `ana` son el mismo).
- Si te equivocas, el mensaje es siempre el mismo («Credenciales no válidas»), exista o no el usuario.
- Tras **5 intentos fallidos seguidos** la cuenta se bloquea **15 minutos**. Un administrador puede desbloquearla
  restableciendo la contraseña. Además, demasiados intentos desde un mismo equipo en poco tiempo se frenan con
  «Demasiadas peticiones» (espera los segundos que indica).
- Las contraseñas tienen al menos **12 caracteres** y no pueden ser una contraseña común (lista de contraseñas
  filtradas) ni el nombre de usuario.
- La sesión caduca tras **60 minutos sin actividad** y, en cualquier caso, **12 horas** después de iniciarla.
- **Cerrar sesión**: menú con tu nombre (arriba a la derecha) → *Cerrar sesión*.

Los valores de bloqueo y caducidad son configurables (`UBW_LOGIN_*`, `UBW_SESSION_*`, ver
[arquitectura](../architecture.md#configuración)).

## Cambiar tu contraseña

Menú con tu nombre → *Cambiar contraseña*. Indica la actual y la nueva dos veces.

- Mínimo 12 caracteres y máximo 128; no puede coincidir con el usuario. Mejor una frase larga que una palabra
  compleja.
- Al cambiarla se **cierran tus demás sesiones** (otros navegadores o equipos); la actual sigue abierta.

## Tema claro u oscuro

Menú con tu nombre → *Tema*: **Claro**, **Oscuro** o **Sistema** (el que tenga configurado tu equipo, y cambia con
él). La opción elegida lleva una marca.

- Se guarda **en tu cuenta**: te acompaña en cualquier navegador o equipo en el que inicies sesión. Las cuentas
  existentes empiezan en *Sistema*.
- Afecta a toda la aplicación, incluidas las vistas previas de Markdown y los diagramas de la documentación.
- Si no se puede guardar, el menú lo avisa y se mantiene el tema anterior.
- La pantalla de inicio de sesión usa el último tema usado en ese navegador; en un navegador nuevo, el del sistema
  hasta que entras.
- Cambiar el tema no se registra en la auditoría.
- Con lector de pantalla, las opciones se anuncian como botones de opción con su estado (marcada o no). Mientras se
  guarda aparecen como no disponibles sin que el foco salga del menú, y un fallo se anuncia como alerta.
- API: el tema llega en `color_scheme` de `GET /api/v1/auth/me` y se cambia con `PATCH /api/v1/auth/me/preferences`
  (`{"color_scheme": "light" | "dark" | "auto"}`, con la cabecera `X-CSRF-Token`). Solo actúa sobre la propia cuenta.

## Administración de usuarios

*Administración → Usuarios* (solo `admin`).

| Acción | Cómo | Efecto |
|---|---|---|
| Crear | *Nuevo usuario*: usuario, nombre visible, rol, contraseña inicial y, desde la 1.22.0, las mismas opciones que al editar (cuenta activa, permisos especiales y cuota) | Comunícale la contraseña por un canal seguro. Si desactivas *Cuenta activa*, se da de alta sin poder iniciar sesión todavía |
| Editar | *Editar* en la fila | Cambia nombre visible o rol |
| Desactivar / reactivar | Interruptor *Cuenta activa* | Desactivar cierra sus sesiones al momento |
| Desbloquear | *Desbloquear* en la fila (solo si está *Bloqueado*) | Quita el bloqueo temporal por intentos fallidos; se audita |
| Eliminar | *Eliminar* en la fila | Ver [Eliminar un usuario](#eliminar-un-usuario) |
| Restablecer contraseña | Campo *Restablecer contraseña* al editar | Cierra todas sus sesiones y quita el bloqueo por intentos |
| Cuota de almacenamiento | Desactiva *Usar la cuota global* y pon su *Cuota propia (MB)* (`0` = sin límite) | Sustituye la cuota general de [Almacenamiento](#almacenamiento) para ese usuario |
| Permisos especiales | *Puede ejecutar SQL libre*, *Puede aplicar DDL* y *Puede escribir datos* al crear o editar | SQL de solo lectura ([explorador](explorador.md)); aplicar migraciones ([migración](migracion.md)) y volcar o cargar datos ([volcado](volcado.md),
[carga](carga.md)) en proyectos de los que sea propietario |

Reglas:

- Siempre debe quedar **al menos un administrador activo**. El único que queda lleva la marca *Único administrador*:
  su rol y su *Cuenta activa* no se pueden cambiar y no tiene *Eliminar*.
- Un administrador no puede desactivarse, quitarse el rol ni eliminarse a sí mismo (pídeselo a otro administrador).
- El estado *Bloqueado* indica un bloqueo temporal por intentos fallidos.
- La lista se filtra por **Rol** y por **Estado** (*Activo*, *Desactivado* o *Bloqueado*), además de la búsqueda por
  usuario o nombre, y la columna *Proyectos* (de los que es miembro) se puede ordenar.

### Eliminar un usuario

*Eliminar* primero comprueba si se puede ([ADR-013](../adr/ADR-013-borrado-de-usuarios.md)). **No** se puede si:

- es tu propia cuenta o el único administrador activo;
- es miembro de algún proyecto (se listan con su rol);
- creó algún proyecto, aunque ya no sea miembro (la carpeta de sus ejecuciones cuelga de su espacio);
- tiene conexiones compartidas o asociadas a algún proyecto.

En ese caso la ventana lo explica y no deja confirmar: quítalo de esos proyectos (o bórralos), o desactiva la cuenta
en su lugar. Si se puede, al confirmar se borran sus sesiones y sus conexiones privadas sin proyectos; sus
ejecuciones y ficheros quedan sin usuario y la auditoría conserva su nombre.

## Almacenamiento

*Administración → Almacenamiento* (solo `admin`, [ADR-012](../adr/ADR-012-almacenamiento-administrable.md)). Cada ajuste
parte de su variable `UBW_*` (se indica junto al campo) y se aplica **sin reiniciar**: la cuota y los límites de la
carga al momento y la retención en la siguiente pasada del worker (cada hora) o al pulsar **Aplicar ahora** (en *Cuota y
retención*). *Restablecer* lo devuelve a la variable. La pantalla tiene dos apartados, cada uno con su
propio **Guardar**: *Cuota y retención* (las cuatro primeras filas de la tabla) y *Carga de ficheros* (la última).

| Ajuste | Qué hace |
|---|---|
| Cuota por usuario (MB) | Espacio de las ejecuciones y ficheros de carga de cada usuario; al llegar, no puede lanzar ni subir (409). `0` = sin límite. Un usuario puede tener una cuota propia |
| Retención de ejecuciones (días) y Ejecuciones por proyecto | Purgan las ejecuciones terminadas más antiguas o que sobran en cada proyecto |
| Retención de ficheros de carga (días) | Borra los ficheros que no use ninguna carga |
| Purga por cuota y su objetivo | Desactivada por defecto. Al llegar a su cuota, se purgan las ejecuciones terminadas más antiguas del usuario hasta bajar al objetivo (80 % por defecto). Nunca las terminadas hace menos de 60 minutos ni las que use una ejecución en curso |
| Carga de ficheros: tamaño máximo, tamaño descomprimido de un Excel y filas máximas | Límites de la [carga](carga.md) (50 MB, 300 MB y 1 000 000 filas por defecto; hasta 2048 MB por fichero). Con un proxy inverso, su límite de cuerpo tiene que ser al menos el tamaño máximo: ver [Ficheros grandes en la carga](deployment.md#ficheros-grandes-en-la-carga) |

Al **Guardar** *Cuota y retención*, la pantalla enseña cuántas ejecuciones y ficheros (y cuánto espacio) purgará la
siguiente pasada con los valores nuevos, y pide confirmación; los límites de la carga se guardan sin ella (no purgan
nada). Purgar una ejecución borra sus ficheros, pero conserva su historial (`run.json`). La tabla **Uso por usuario**
muestra el espacio de cada uno frente a su cuota. Cada usuario ve el suyo en su menú → **Mi espacio**.

## Ejecuciones de todos los proyectos

*Administración → Todas las ejecuciones* lista las ejecuciones de **todos** los proyectos, también de los que no eres
miembro, con proyecto, operación, estado, usuario, tamaño y fecha. Solo los datos de la ejecución: sus parámetros,
mensajes y ficheros siguen sin verse si no eres miembro del proyecto.

- **Eliminar** borra una ejecución por completo (fila, ficheros y carpeta); desaparece del historial y no se puede
  deshacer. Hay que escribir `ELIMINAR` para confirmarlo. No se pueden eliminar las que están en cola o en curso
  (cancélalas antes) ni un volcado que dejó constraints sin restaurar en el destino (restáuralas antes).
- **Todas las del proyecto** borra las ejecuciones terminadas de ese proyecto (el proyecto no se borra). El aviso dice
  cuántas son y cuánto espacio ocupan, y hay que escribir el **nombre exacto del proyecto** (el servidor lo comprueba
  también). Las que están en cola o en curso y los volcados con constraints pendientes se omiten, y el resultado dice
  cuántas se borraron, cuántas se omitieron y por qué.

Cada borrado queda en la **auditoría** (`run.delete` y `project.runs_delete`) con el resumen de lo borrado.

## Listas

Desde la 1.14.0 todas las listas (usuarios, sesiones, auditoría, uso de almacenamiento, destinos permitidos, queries
nombradas, motores, conexiones, proyectos, sus miembros y conexiones, plantillas y ejecuciones) se **ordenan**
pulsando la cabecera de una columna (ascendente, descendente y sin orden, en ese orden), muestran **25 filas por
página** con el recuento («26-50 de 312») y tienen **búsqueda**. La búsqueda trata `%` y `_` como texto, no como
comodines.

## Sesiones activas

*Administración → Sesiones* lista las sesiones abiertas de todos los usuarios: IP, navegador, inicio, última
actividad y caducidad. *Esta sesión* marca la tuya.

**Revocar** pide confirmación y cierra esa sesión de inmediato: el usuario tendrá que volver a iniciar sesión. Si
revocas la tuya, saldrás de la aplicación.

## Auditoría

*Administración → Auditoría* muestra los eventos más recientes primero, filtrables por *Tipo de acción* y con
búsqueda por acción, actor, objetivo o IP:

| Tipo | Eventos |
|---|---|
| Autenticación | Inicio de sesión (correcto o fallido, con el motivo), bloqueo de cuenta, cierre de sesión, cambio de contraseña |
| Usuarios | Alta (con permisos y cuota), edición (campos cambiados), desactivación, reactivación, contraseña restablecida, desbloqueo, borrado |
| Sesiones | Sesión revocada |
| Conexiones | Alta, edición, borrado, prueba y readiness |
| Destinos | Destino permitido añadido o retirado |
| Proyectos | Alta, edición y borrado; miembros añadidos, quitados o con otro rol; conexiones asociadas o quitadas; borrado de todas sus ejecuciones (`project.runs_delete`) |
| Ejecuciones | Lanzada, cancelada, purgada y eliminada (`run.delete`) |
| SQL | Cada consulta de SQL libre, con su texto (recortado) |
| Queries | Query nombrada ejecutada, creada, editada o borrada |

Con *Todas* se ven también los eventos sin filtro propio: plantillas (`template.*`), ficheros de carga
(`upload.*`) y ajustes y mantenimiento del almacenamiento (`storage.*`).

*Sistema* en la columna *Quién* indica una acción sin usuario (CLI o intento de login fallido). La auditoría nunca
guarda contraseñas ni tokens.
