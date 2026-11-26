# Usuarios, sesiones y auditoría

Guía de uso de la identidad multiusuario. Disponible desde la versión 0.2.0 (Fase 1); vigente en 2.1.0.

## Roles y permisos

Desde la 2.0.0 cada usuario tiene un **rol**, y el rol decide qué puede hacer además de usar la aplicación
([ADR-014](../adr/ADR-014-roles-y-permisos.md)). Todos pueden iniciar sesión, cambiar su contraseña, elegir tema e
idioma y trabajar en los proyectos de los que son miembros (el acceso a cada proyecto sigue siendo por miembros:
propietario, editor o lector).

| Permiso | Permite |
|---|---|
| Gestionar usuarios | *Administración → Usuarios*: alta, edición, borrado, transferencia y desbloqueo |
| Gestionar roles | *Administración → Roles* |
| Gestionar sesiones | *Administración → Sesiones* |
| Ver la auditoría | *Administración → Auditoría* |
| Gestionar plantillas globales | *Administración → Plantillas* |
| Gestionar queries nombradas | *Administración → Queries nombradas* |
| Gestionar destinos permitidos | *Administración → Destinos permitidos* |
| Gestionar el almacenamiento | *Administración → Almacenamiento* |
| Administrar ejecuciones | *Administración → Ejecuciones de todos los proyectos* |
| Compartir conexiones | Crear y gestionar conexiones compartidas |
| Ejecutar SQL libre | SQL de solo lectura en el [explorador](explorador.md) |
| Aplicar DDL | Aplicar migraciones ([migración](migracion.md)) en proyectos de los que sea propietario |
| Escribir datos | Volcar y cargar datos ([volcado](volcado.md), [carga](carga.md)) en proyectos de los que sea propietario |

Hay dos **roles base**: *Administrador* (todos los permisos) y *Usuario* (ninguno). No se pueden cambiar ni borrar.
El menú *Administración* muestra solo las secciones que permite tu rol.

El primer administrador se crea por línea de comandos ([despliegue](deployment.md#primer-administrador)); no existen
credenciales por defecto.

### Gestionar roles

*Administración → Roles* (permiso *Gestionar roles*). La lista muestra cada rol con sus permisos y cuántos usuarios
lo tienen.

- **Nuevo rol**: nombre y permisos, agrupados en *Administración* y *Conexiones y bases de datos*. Los permisos que tú
  no tienes salen desactivados: nadie da ni quita un permiso que no tiene.
- **Editar**: cambia el nombre o los permisos. **Quitar permisos cierra las sesiones** de los usuarios con ese rol
  (dejan de valer al momento); añadirlos no.
- **Borrar**: solo un rol sin usuarios (asígnales otro antes).
- Todo se registra en la auditoría (`role.create`, `role.update`, `role.delete`).

Al actualizar a la 2.0.0, los administradores pasan al rol *Administrador* (que también incluye SQL libre, aplicar
DDL y escribir datos), los usuarios sin permisos especiales al rol *Usuario*, y los que tenían alguno a un rol con
exactamente esos permisos («Usuario + SQL», «Usuario + DDL + datos»…), que puedes renombrar.

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

## Idioma

Menú con tu nombre → *Idioma*: **Español** o **English**. Cada opción aparece en su propio idioma.

- Se guarda **en tu cuenta**, como el tema, y se aplica al momento a toda la interfaz, incluidas las fechas y los
  números.
- La pantalla de inicio de sesión usa el último idioma usado en ese navegador; en un navegador nuevo, el del
  navegador (inglés si lo prefiere, y si no, español).
- Los **mensajes de error** del servidor (título, detalle y errores de cada campo) y el motivo del fallo de una
  ejecución llegan en tu idioma; el de una ejecución lo ve cada miembro del proyecto en el suyo
  ([ADR-015](../adr/ADR-015-idioma-de-los-mensajes-de-la-api.md)).
- **Qué sigue en español** con la interfaz en inglés: el progreso de las ejecuciones y su log, los avisos de la
  documentación, los textos que vienen de util_bbdd dentro de un mensaje (p. ej. el motivo por el que rechaza un
  plan), el motivo del fallo de las ejecuciones anteriores a la 2.1.0 y los documentos que se generan, cuyo idioma
  se elige al lanzarlos (parámetro *Idioma*).
- API: `language` en `GET /api/v1/auth/me` y `PATCH /api/v1/auth/me/preferences` (`{"language": "es" | "en"}`,
  junto con `color_scheme` o por separado).

## Administración de usuarios

*Administración → Usuarios* (permiso *Gestionar usuarios*).

| Acción | Cómo | Efecto |
|---|---|---|
| Crear | *Nuevo usuario*: usuario, nombre visible, rol, contraseña inicial, cuenta activa y cuota | Comunícale la contraseña por un canal seguro. Si desactivas *Cuenta activa*, se da de alta sin poder iniciar sesión todavía |
| Editar | *Editar* en la fila | Cambia nombre visible o rol. Cambiar el rol cierra sus sesiones |
| Desactivar / reactivar | Interruptor *Cuenta activa* | Desactivar cierra sus sesiones al momento |
| Desbloquear | *Desbloquear* en la fila (solo si está *Bloqueado*) | Quita el bloqueo temporal por intentos fallidos; se audita |
| Eliminar | *Eliminar* en la fila | Ver [Eliminar un usuario](#eliminar-un-usuario) |
| Restablecer contraseña | Campo *Restablecer contraseña* al editar | Cierra todas sus sesiones y quita el bloqueo por intentos |
| Cuota de almacenamiento | Desactiva *Usar la cuota global* y pon su *Cuota propia (MB)* (`0` = sin límite) | Sustituye la cuota general de [Almacenamiento](#almacenamiento) para ese usuario |

Reglas:

- Siempre debe quedar **al menos un usuario activo con el rol *Administrador***. El único que queda lleva la marca
  *Único administrador*: su rol y su *Cuenta activa* no se pueden cambiar y no tiene *Eliminar*.
- Nadie puede desactivarse, cambiar su propio rol ni eliminarse a sí mismo (pídeselo a otro administrador).
- Solo puedes asignar roles cuyos permisos tienes, y no puedes cambiar el rol de quien tiene permisos que tú no
  tienes: esas opciones salen desactivadas.
- El estado *Bloqueado* indica un bloqueo temporal por intentos fallidos.
- La lista se filtra por **Rol** y por **Estado** (*Activo*, *Desactivado* o *Bloqueado*), además de la búsqueda por
  usuario o nombre, y la columna *Proyectos* (de los que es miembro) se puede ordenar.

### Eliminar un usuario

*Eliminar* primero comprueba si se puede ([ADR-013](../adr/ADR-013-borrado-de-usuarios.md)). **No** se puede si:

- es tu propia cuenta o el único administrador activo;
- es miembro de algún proyecto (se listan con su rol);
- creó algún proyecto, aunque ya no sea miembro (la carpeta de sus ejecuciones cuelga de su espacio);
- tiene conexiones compartidas o asociadas a algún proyecto.

En ese caso la ventana lo explica y no deja confirmar: quítalo de esos proyectos (o bórralos), **transfiérelos**, o
desactiva la cuenta en su lugar. Si se puede, al confirmar se borran sus sesiones y sus conexiones privadas sin proyectos; sus
ejecuciones y ficheros quedan sin usuario y la auditoría conserva su nombre.

### Transferir proyectos y conexiones

Desde la ventana de *Eliminar*, **Transferir…** cede a otro usuario activo:

- los proyectos que creó: pasan a colgar de la carpeta del destino (se mueven sus ejecuciones, ficheros y plantillas);
- la propiedad de los proyectos de los que es propietario;
- sus conexiones compartidas o asociadas a proyectos (las compartidas, solo a un administrador). Sus conexiones
  privadas sin uso no se ceden y se borrarán con la cuenta.

Con *Quitarlo además de todos los proyectos* (activado por defecto) también deja de ser miembro de los demás, y
después se puede eliminar. La vista previa enseña qué se mueve y los nombres que cambian si el destino ya tiene un
proyecto o una conexión con el mismo nombre (se añade « (de <usuario>)»). No se puede transferir si hay ejecuciones
en cola o en curso en un proyecto que creó.

## Almacenamiento

*Administración → Almacenamiento* (permiso *Gestionar el almacenamiento*, [ADR-012](../adr/ADR-012-almacenamiento-administrable.md)). Cada ajuste
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
| Usuarios | Alta (con permisos y cuota), edición (campos cambiados), desactivación, reactivación, contraseña restablecida, desbloqueo, borrado, transferencia |
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
