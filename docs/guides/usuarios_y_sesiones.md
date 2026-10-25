# Usuarios, sesiones y auditoría

Guía de uso de la identidad multiusuario. Disponible desde la versión 0.2.0 (Fase 1); vigente en 1.0.0.

## Roles

| Rol | Puede |
|---|---|
| `user` | Iniciar y cerrar sesión, cambiar su contraseña y usar las secciones de la aplicación |
| `admin` | Lo anterior y, además, gestionar usuarios, ver y revocar sesiones y consultar la auditoría |

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

## Administración de usuarios

*Administración → Usuarios* (solo `admin`).

| Acción | Cómo | Efecto |
|---|---|---|
| Crear | *Nuevo usuario*: usuario, nombre visible, rol y contraseña inicial | Usuario activo; comunícale la contraseña por un canal seguro |
| Editar | *Editar* en la fila | Cambia nombre visible o rol |
| Desactivar / reactivar | Interruptor *Cuenta activa* | Desactivar cierra sus sesiones al momento; los usuarios no se borran para conservar la auditoría |
| Restablecer contraseña | Campo *Restablecer contraseña* al editar | Cierra todas sus sesiones y quita el bloqueo por intentos |
| Cuota de almacenamiento | Desactiva *Usar la cuota global* y pon su *Cuota propia (MB)* (`0` = sin límite) | Sustituye la cuota general de [Almacenamiento](#almacenamiento) para ese usuario |
| Permisos especiales | *Puede ejecutar SQL libre*, *Puede aplicar DDL* y *Puede escribir datos* al editar | SQL de solo lectura ([explorador](explorador.md)); aplicar migraciones ([migración](migracion.md)) y volcar o cargar datos ([volcado](volcado.md),
[carga](carga.md)) en proyectos de los que sea propietario |

Reglas:

- Siempre debe quedar **al menos un administrador activo**.
- Un administrador no puede desactivarse ni quitarse el rol a sí mismo (pídeselo a otro administrador).
- El estado *Bloqueado* indica un bloqueo temporal por intentos fallidos.

## Almacenamiento

*Administración → Almacenamiento* (solo `admin`, [ADR-012](../adr/ADR-012-almacenamiento-administrable.md)). Cada ajuste parte de su variable `UBW_*` (se indica junto al campo) y se aplica **sin reiniciar**: la cuota al momento y la retención en la siguiente pasada del worker (cada hora) o al pulsar **Aplicar ahora**. *Restablecer* lo devuelve a la variable.

| Ajuste | Qué hace |
|---|---|
| Cuota por usuario (MB) | Espacio de las ejecuciones y ficheros de carga de cada usuario; al llegar, no puede lanzar ni subir (409). `0` = sin límite. Un usuario puede tener una cuota propia |
| Retención de ejecuciones (días) y Ejecuciones por proyecto | Purgan las ejecuciones terminadas más antiguas o que sobran en cada proyecto |
| Retención de ficheros de carga (días) | Borra los ficheros que no use ninguna carga |
| Purga por cuota y su objetivo | Desactivada por defecto. Al llegar a su cuota, se purgan las ejecuciones terminadas más antiguas del usuario hasta bajar al objetivo (80 % por defecto). Nunca las terminadas hace menos de 60 minutos ni las que use una ejecución en curso |

Al **Guardar**, la pantalla enseña cuántas ejecuciones y ficheros (y cuánto espacio) purgará la siguiente pasada con los valores nuevos, y pide confirmación. Purgar una ejecución borra sus ficheros, pero conserva su historial (`run.json`). La tabla **Uso por usuario** muestra el espacio de cada uno frente a su cuota. Cada usuario ve el suyo en su menú → **Mi espacio**.

## Sesiones activas

*Administración → Sesiones* lista las sesiones abiertas de todos los usuarios: IP, navegador, inicio, última
actividad y caducidad. *Esta sesión* marca la tuya.

**Revocar** pide confirmación y cierra esa sesión de inmediato: el usuario tendrá que volver a iniciar sesión. Si
revocas la tuya, saldrás de la aplicación.

## Auditoría

*Administración → Auditoría* muestra los eventos más recientes primero, filtrables por tipo:

| Tipo | Eventos |
|---|---|
| Autenticación | Inicio de sesión (correcto o fallido, con el motivo), bloqueo de cuenta, cierre de sesión, cambio de contraseña |
| Usuarios | Alta, edición (campos cambiados), desactivación, reactivación, contraseña restablecida |
| Sesiones | Sesión revocada |

*Sistema* en la columna *Quién* indica una acción sin usuario (CLI o intento de login fallido). La auditoría nunca
guarda contraseñas ni tokens.
