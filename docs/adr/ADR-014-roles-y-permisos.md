# ADR-014 — Roles y permisos

- **Estado**: Aceptado
- **Fecha**: 2026-11-25
- **Modifica**: [ADR-003](ADR-003-autenticacion-sesiones.md) (los roles dejan de ser `admin`/`user`) y los permisos
  `can_*` de [ADR-008](ADR-008-aplicar-migraciones.md), [ADR-009](ADR-009-volcado-de-datos.md) y
  [ADR-010](ADR-010-carga-bulk.md)
- **Antecedente**: ADR-013 «Multi-tenant y roles» de doc_organize_web (2.0, Fase 9)

## Contexto

Hasta la 1.24 la autorización era un rol fijo por usuario (`admin` o `user`) y tres casillas sueltas:
`can_run_sql`, `can_apply_ddl` y `can_write_data`. No se podía delegar una parte de la administración (por ejemplo,
la auditoría o las sesiones) sin dar todo, y había unas 25 comparaciones con `role == "admin"` repartidas por el
backend y el frontend.

doc_organize_web resolvió lo mismo en su 2.0 con roles administrables dentro de cada tenant. Aquí no hay tenants, así
que se toma solo la parte de roles.

## Decisión

1. **Un rol por usuario, con permisos de un catálogo fijo** (`app/domain/identity/permissions.py`):

    | Grupo | Permisos |
    |---|---|
    | Administración | `users.manage`, `roles.manage`, `sessions.manage`, `audit.read`, `templates.manage`, `queries.manage`, `allowlist.manage`, `storage.manage`, `runs.admin` |
    | Conexiones y bases de datos | `connections.share`, `sql.run` (antes `can_run_sql`), `ddl.apply` (antes `can_apply_ddl`), `data.write` (antes `can_write_data`) |

    El acceso a cada proyecto sigue siendo por miembros (`owner`/`editor`/`viewer`), y la cuota de almacenamiento es
    de cada usuario. Ver los roles exige `roles.manage` o `users.manage` (para asignarlos).

2. **Dos roles base** que no se borran ni cambian (de permisos ni de nombre): «Administrador» (`builtin='admin'`, **todos** los
   permisos, también los que se añadan al catálogo) y «Usuario» (`builtin='user'`, ninguno). Su nombre en la interfaz
   sale de las traducciones.

3. **Salvaguardas**:
    - nadie da ni quita un permiso que no tiene: crear o cambiar un rol, asignarlo a un usuario o cambiar el rol de
      quien tiene más permisos responde `403`;
    - nadie cambia su propio rol ni se desactiva (`409`);
    - siempre queda al menos un usuario activo con el rol «Administrador» (`409`, con recuento tras escribir como en
      la 1.22.0);
    - un rol con usuarios no se borra (`409`);
    - cambiar el rol de un usuario, o quitar permisos a un rol, cierra sus sesiones;
    - todo se audita (`role.create`, `role.update`, `role.delete`, `user.update` con `role: [antes, después]`).

4. **Comprobación centralizada**: los routers usan `require_permission(...)` (`UserManager`, `RoleManager`,
   `AuditReader`…) y el dominio `user.can("...")`. Un test de arquitectura impide volver a `role == "admin"`,
   `require_admin` o a leer los `can_*`.

5. **Migración `0014`** sin recrear `users` (como la 0012 y la 0013):
    - crea `roles` y `users.role_id` (con `ALTER TABLE`, sin `REFERENCES`: SQLite no permite después `DROP COLUMN` de
      una columna con FK; la integridad la garantiza la aplicación);
    - los `admin` reciben «Administrador», los `user` sin casillas «Usuario», y cada combinación de casillas
      existente un rol propio («Usuario + SQL», «Usuario + DDL + datos»…) con sus permisos;
    - `users.role` y `users.can_*` se quedan sin uso y la aplicación los mantiene **en sincronía** con el rol, para
      poder volver a la imagen 1.24.0 sin perder permisos. El `downgrade` los rellena desde el rol.

## Consecuencias

- **Cambio incompatible en la API**: `Me` y `UserOut` sustituyen `role` (`admin`/`user`) y `can_*` por
  `role: {id, name, builtin}` y `permissions`; `UserCreate`/`UserUpdate` reciben `role_id`; `GET /users` filtra por
  `role_id`; el motivo de transferencia `target_not_admin` pasa a ser `target_cannot_share`.
- **Los administradores ganan SQL libre, aplicar DDL y escribir datos** si no los tenían: «Administrador» lo tiene
  todo. Antes podían activárselos a sí mismos, así que no cambia lo que un administrador puede llegar a hacer
  (decisión de la sesión 2026-11-25-roles-idioma).
- Un permiso nuevo en el catálogo lo tiene de inmediato «Administrador»; los roles personalizados no lo tienen hasta
  que alguien se lo dé.
- Fuera de alcance: varios roles por usuario, permisos por proyecto en el rol, cuota por rol y tenants.
