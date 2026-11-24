# TRACEABILITY

## Session metadata
- id: 2026-11-24-usuarios-borrado
- fecha: 2026-11-24
- rama: develop
- skill: new_feature + audit_code + version_closure
- fase: PLAN v1 + AUDIT_PLAN (GO_CONDICIONAL) → PLAN v2 con todas las mejoras + AUDIT_PLAN v2 (GO_CONDICIONAL,
  aprobado con las propuestas por defecto) → IMPLEMENT entrega A → AUDIT_CODE (APROBADO CON CONDICIONES; m1 y n1
  corregidos) → VERSION (sin subir versión: 1.22.0 se publicará con la entrega B)

## Prompt issued
«Ampliar funcionalidad de usuarios: permitir borrar usuarios, si es miembro de un proyecto avisar mostrando los
proyectos y no permitir su borrado; controlar que siempre exista un administrador activo […]; al dar de alta permitir
seleccionar las opciones como en editar; búsqueda también por rol y estado; en proyectos, apartado miembros, que al
teclear aparezcan los usuarios que corresponden; en ejecuciones, ordenar por proyecto. Puedes proponer mejoras. PLAN y
AUDIT_PLAN» → «Incluir todas las mejoras, nuevo PLAN y AUDIT_PLAN» → «adelante, implementa la entrega A» →
«AUDIT_CODE y VERSION».

## Context supplied
- Web 1.21.1 + util_bbdd 5.9.1 (commit `64975d4`). Regla existente del último admin en `users.update_user`
  (`LastAdminError`, `SelfModificationError`); ADR-003 «los usuarios no se borran»; ADR-005 «la carpeta es la del
  creador del proyecto».
- FK hacia `users`: `CASCADE` en `sessions`, `project_members`, `projects.owner_id`, `connections.owner_id`; `SET NULL`
  en `audit_log.actor_user_id`, `runs.user_id`, `uploads.user_id` y los `created_by`/`added_by`/`updated_by`.
- PLAN v2 resumido en [PLAN.md](PLAN.md).

## AI output summary
- PLAN v1: detectado que bloquear solo por pertenencia no basta (`CASCADE` de `projects.owner_id` y
  `connections.owner_id`). PLAN v2: entregas A y B; la transferencia (B) exige mover carpetas del workspace.
- Backend:
  - `domain/identity/users.py`: `list_users` con `role`, `status` (`locked` = activo con `locked_until` futuro) y
    `project_count` (subconsulta correlacionada, ordenable); `count_active_admins` (antes `_active_admins`);
    `create_user` con estado, permisos y cuota; `_ensure_active_admin` (recuento tras `flush`, rollback si 0) en
    `update_user` y `delete_user`; `unlock_user`; `deletion_check` / `DeletionCheck`; `delete_user` (toma el bloqueo
    de escritura antes de comprobar, audita `user.delete`, borra `users/<id>/` si no tiene ficheros).
  - `errors.py`: `SelfDeletionError`, `UserInUseError` (extra `reasons`, `projects`, `created_projects`,
    `connections`). `audit.py`: `USER_UNLOCK`, `USER_DELETE`; `record` guarda `actor_name`; búsqueda y orden por
    actor con `coalesce(User.username, AuditEntry.actor_name)`.
  - `models.py`: `AuditEntry.actor_name` y `actor_username` con respaldo. Migración `0013_audit_actor_name.py`
    (`ADD COLUMN` + backfill; `DROP COLUMN` en el downgrade).
  - API: `users.py` (filtros, `_out` con `project_count`, `unlock`, `deletion-check`, `DELETE`), `schemas.py`
    (`UserCreate` ampliado, `UserPage.active_admins`, `UserDeletionCheck`, `BlockingProject`, `BlockingConnection`),
    `projects.py` + `schemas_projects.py` (`member-candidates`, `MemberCandidate`), `runs/service.py`
    (`sort=project`, unión con `Project` en `_base_runs`).
- Contrato: `openapi/openapi.json` exportado y `frontend/src/api/schema.d.ts` regenerado.
- Frontend: `DeleteUserModal.tsx` (nuevo); `UsersPage.tsx` (filtros en `toolbar`, columna *Proyectos*, *Único
  administrador*, *Desbloquear*, *Eliminar* salvo el último admin y la propia cuenta); `UserFormModal.tsx` (opciones
  en el alta, rol y estado desactivados para el último admin); `useAdmin.ts` (`UserFilters`, `useDeletionCheck`,
  `useDeleteUser`, `useUnlockUser`); `ProjectTabs.tsx` + `useProjects.ts` (`Autocomplete` con retardo de 300 ms y
  `useMemberCandidates`); `RunsTable.tsx` (proyecto ordenable); i18n.
- Desviaciones del PLAN v2: migración 0013 (no prevista: sin ella las acciones de un usuario borrado aparecían como
  «Sistema»); proyectos y conexiones del modal como texto (un admin recibe 404 en los ajenos); escritura previa en
  `delete_user` para cerrar la carrera comprobación-borrado.
- Docs: ADR-013 (nuevo), nota en ADR-003, `usuarios_y_sesiones.md` (+ «Eliminar un usuario»),
  `proyectos_y_ejecuciones.md`, `deployment.md` (revisión 0013), `README.md`, `architecture.md`, `zensical.toml`,
  `CHANGELOG.md` (`[Unreleased]`).
- Tests: backend `test_user_lifecycle.py` (15, nuevo), `test_projects.py` (+2), `test_list_sorting.py` (+1),
  `test_cli_and_migrations.py` (+1, 0013), `test_backup.py` (revisión 0013); frontend `admin.test.tsx` (+8 y 3
  adaptados), `projects.test.tsx` (miembro por sugerencia).
- AUDIT_CODE: m1 (al borrar, invalidar `['users']` repetía `deletion-check` del usuario borrado → 404 visible un
  instante) corregido con la clave `['user-deletion-check', id]`; n1 (*Eliminar* en la propia fila) corregido. Ambos
  con test de regresión.
- Validaciones ejecutadas: ruff format/check, mypy, pytest completo (844 passed, 101 skipped; los 6 `ERROR` de la
  primera pasada eran del flag `-p no:logging`, repetidos sin él pasan; el `FAILED` de `test_backup.py` se corrigió y
  ese fichero pasa), `export_openapi.py --check`, frontend format:check, lint, typecheck, Vitest 254/254 (antes de
  m1/n1; después, `src/features/admin` 24/24), `npm run build`, `zensical build --strict`. No ejecutados:
  `docker compose up --build` + `/api/health`, Playwright.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN v2 + AUDIT_PLAN | [PLAN.md](PLAN.md) | aprobado |
| IMPLEMENT (A) | `backend/…` · `frontend/…` · `openapi/openapi.json` · `docs/…` | completado |
| ADR | `docs/adr/ADR-013-borrado-de-usuarios.md` | aceptado |
| Migración | `backend/alembic/versions/0013_audit_actor_name.py` | completado |
| Log de pytest | `build/logs/pytest-usuarios.txt` (primera pasada) | informativo |

## Directrices para Futuras IAs
- **[usuarios]**: borrar un usuario lo bloquean la pertenencia a proyectos, ser creador (`projects.owner_id`, aunque
  ya no sea miembro) y las conexiones compartidas o asociadas a proyectos; todas por `ON DELETE CASCADE`. Cualquier
  nueva FK hacia `users` con `CASCADE` debe añadirse a `deletion_check` en `domain/identity/users.py`.
- **[usuarios]**: el «último admin activo» se comprueba antes y se vuelve a contar tras `flush` (`_ensure_active_admin`);
  los admins bloqueados por intentos cuentan como activos.
- **[sqlite]**: con pysqlite en modo heredado, un `SELECT` no abre transacción; la primera escritura sí y toma el
  bloqueo de escritura. `delete_user` escribe `updated_at` antes de comprobar para serializar contra otros escritores.
- **[auditoría]**: `audit.record` guarda `actor_name` (consulta `db.get(User, actor_id)`); `AuditEntryOut.actor_username`
  cae a ese nombre si el usuario ya no existe. La migración 0013 rellena los eventos anteriores.
- **[frontend]**: `Select` y `Autocomplete` de Mantine 9 exponen `role="combobox"`, y sus opciones (portal) solo se
  encuentran con `findByRole('option', { …, hidden: true })`. Mantine no admite `''` como valor de opción: los
  filtros usan el centinela `all`.
- **[frontend]**: no usar claves bajo `['users', …]` para consultas por usuario que no deban recargarse al invalidar la
  lista (p. ej. `['user-deletion-check', id]`).
- **[tests]**: en Windows, Vitest solo arranca desde `C:\…` (letra de unidad en mayúscula); con todos los ficheros en
  paralelo algunos tests superan los 5 s: `--no-file-parallelism` los estabiliza. No lanzar pytest con
  `-p no:logging` (rompe los tests que usan `caplog`).
- **[entrega B]**: transferir un proyecto exige mover `users/<origen>/projects/<id>` y reescribir el prefijo de
  `runs.workspace_path` y `uploads.path`; las plantillas calculan su ruta desde `owner_id` y los artefactos son
  relativos al run. Bloquear si hay ejecuciones en cola o en curso (como `delete_project`).

## Veredicto final
Veredicto: CLOSED (entrega A)
Pendientes al cierre:
- Entrega B (transferencia de proyectos y conexiones) con su PLAN propio y AUDIT_CODE.
- Publicar 1.22.0 (versión en los siete sitios de `sync.instructions.md`) tras la entrega B o antes si se decide.
- `docker compose up -d --build` + `/api/health` y Playwright antes de publicar.
- Commits propuestos, no ejecutados.
