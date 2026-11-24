# ADR-013 — Borrado de usuarios sin dependencias

- **Estado**: Aceptado
- **Fecha**: 2026-11-24
- **Modifica**: [ADR-003](ADR-003-autenticacion-sesiones.md) (los usuarios ya no son solo desactivables)

## Contexto

Hasta la 1.21 un usuario no se borraba: se desactivaba, porque la auditoría lo referencia. Los administradores
necesitan eliminar cuentas creadas por error o de personas que ya no usan la aplicación. Las claves foráneas hacia
`users` ya existen desde la 0004 y el borrado en cascada está activo (`PRAGMA foreign_keys=ON`):

| Tabla | Al borrar el usuario |
|---|---|
| `sessions`, `project_members` | `CASCADE` |
| `projects.owner_id` (creador) | `CASCADE`: se perderían el proyecto, sus ejecuciones y ficheros |
| `connections.owner_id` | `CASCADE`: se perderían conexiones compartidas o asociadas a proyectos de otros |
| `audit_log.actor_user_id`, `runs.user_id`, `uploads.user_id`, `*.created_by`… | `SET NULL` |

Además, la carpeta de un proyecto en el workspace cuelga de la del creador (`users/<owner_id>/projects/<id>`, ADR-005).

## Decisión

1. **Borrar solo si nada depende del usuario.** `DELETE /api/v1/users/{id}` (admin, CSRF) responde `409` si:
    - es la cuenta del propio admin (`self`);
    - es el último administrador activo (`last_admin`);
    - es miembro de algún proyecto (`member`);
    - creó algún proyecto, aunque ya no sea miembro (`creator`);
    - tiene conexiones compartidas o asociadas a algún proyecto (`connections`).

    El *problem details* del `409` lleva `reasons`, `projects` (`id`, `name`, `role`), `created_projects` y
    `connections` (`id`, `name`, `visibility`, nunca parámetros ni secretos). `GET /api/v1/users/{id}/deletion-check`
    devuelve lo mismo antes de intentarlo, para la confirmación de la interfaz.
2. **Qué se borra**: sesiones y conexiones privadas sin proyectos (con su secreto cifrado). Ejecuciones, ficheros,
   plantillas, queries y destinos permitidos que lo citan quedan sin usuario. La carpeta `users/<id>/` se borra si no
   contiene ficheros (sin proyectos creados no debería tenerlos); si los tiene, se conserva y se avisa en el log.
3. **Auditoría con nombre**: `audit_log.actor_name` (migración 0013, rellenada con el nombre de cada actor) guarda el
   nombre al registrar el evento; la API lo muestra cuando el usuario ya no existe. El borrado se audita como
   `user.delete` con el nombre, el rol y cuántas conexiones privadas se borraron.
4. **Siempre un administrador activo**: además de la comprobación previa (ya existente al editar), tras escribir se
   vuelve a contar y, si no queda ninguno, se deshace la operación. Cubre dos peticiones simultáneas que vieran dos
   administradores y quitaran uno cada una.
5. **Sin carreras entre comprobar y borrar**: el borrado escribe primero en la fila del usuario, lo que toma el
   bloqueo de escritura de SQLite; nadie puede añadirlo a un proyecto ni asociar sus conexiones entre la comprobación
   y el `DELETE` (los `CASCADE` las borrarían sin aviso).
6. **Desbloqueo manual**: `POST /api/v1/users/{id}/unlock` quita el bloqueo por intentos fallidos (se audita como
   `user.unlock`).

## Consecuencias

- **Positivas**: se pueden limpiar cuentas sin perder datos de otros; la auditoría sigue atribuyendo las acciones.
- **Negativas**:
    - Un nombre de usuario borrado puede volver a darse de alta; la auditoría distingue por `target_id` y el evento
      `user.delete`, pero `actor_name` solo guarda el nombre.
    - Para borrar a quien creó proyectos hay que borrarlos o, en el futuro, transferirlos (la transferencia mueve
      carpetas del workspace y queda para otra entrega).
    - La lista de proyectos del `409` la ve un admin aunque no sea miembro de ellos (solo id y nombre).

## Alternativas descartadas

- **Borrado lógico** (marcar como borrado): equivale a desactivar, que ya existe.
- **Bloquear solo por pertenencia a proyectos**: el `CASCADE` de `projects.owner_id` y `connections.owner_id` borraría
  proyectos y conexiones de otros.
- **No guardar el nombre en la auditoría**: las acciones del usuario borrado aparecerían como del sistema.
