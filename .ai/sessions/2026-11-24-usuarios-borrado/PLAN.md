# PLAN (v2) — Gestión de usuarios: borrado, último administrador, alta completa, filtros y sugerencias

Aprobado el 2026-11-24 («adelante, implementa la entrega A»). Sustituye a la v1, que solo bloqueaba el borrado por
pertenencia a proyectos: con `projects.owner_id` y `connections.owner_id` en `ON DELETE CASCADE`, borrar al creador o
al dueño de conexiones se llevaba proyectos y conexiones de otros.

## Petición

Borrar usuarios (no si es miembro de proyectos, mostrándolos); siempre un administrador activo; alta con las opciones
de la edición; búsqueda por rol y estado; sugerencias al añadir miembros; ordenar ejecuciones por proyecto. Mejoras
propuestas y aceptadas: M1 estado «Bloqueado» y desbloqueo, M2 columna «Proyectos», M3 transferencia, M4 alta inactiva.

## Entregas

| Entrega | Alcance | Estado |
|---|---|---|
| A | R1–R6, M1, M2, M4 | Implementada (esta sesión) |
| B | M3: transferir proyectos (mueve `users/<origen>/projects/<id>` → `users/<destino>/…`, reescribe `runs.workspace_path` y `uploads.path`) y conexiones | Pendiente |

## Contrato HTTP (entrega A)

| Endpoint | Cambio |
|---|---|
| `GET /users` | `role`, `status=active\|inactive\|locked`, `sort=projects`; `UserOut.project_count`, `UserPage.active_admins` |
| `POST /users` | `is_active`, `can_run_sql`, `can_apply_ddl`, `can_write_data`, `storage_quota_mb` (opcionales) |
| `GET /users/{id}/deletion-check` | `{can_delete, reasons[], projects[], created_projects[], connections[]}` |
| `DELETE /users/{id}` | 204; 409 con el mismo detalle, `self` o `last_admin` |
| `POST /users/{id}/unlock` | 200 `UserOut`; auditado como `user.unlock` |
| `GET /projects/{id}/member-candidates?q=` | `[{username, display_name}]`, solo `owner`, `q` ≥ 2, máximo 10 |
| `GET /runs`, `GET /projects/{id}/runs` | `sort=project` |

## Decisiones de AUDIT_PLAN v2

- Sugerencias de miembros para propietarios con mitigaciones (mínimo 2 caracteres, 10 resultados, solo usuario y
  nombre visible de usuarios activos); se acepta el riesgo de enumeración (ya existía probando nombres al añadir).
- Recuento de administradores activos tras escribir, para la carrera de dos peticiones.
- Dos entregas: A sin tocar el disco salvo la carpeta vacía del usuario borrado; B con su propio AUDIT_CODE.
