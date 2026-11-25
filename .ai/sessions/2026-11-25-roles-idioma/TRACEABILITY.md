# TRACEABILITY

## Session metadata
- id: 2026-11-25-roles-idioma
- fecha: 2026-11-25 (cierre 2026-11-26)
- rama: feat/roles-idioma (sobre `031b005`, release 1.24.0)
- skill: new_feature + audit_code + version_closure
- fase: PLAN + AUDIT_PLAN (GO_CONDICIONAL; D1 todo en una versión, D2 `can_*` dentro de los roles, D3 retirar
  `role`/`can_*` de la API, D4 13 permisos, D5 es/en con `en-GB`, D6 solo interfaz) → IMPLEMENT → AUDIT_CODE
  (escalada por restablecer contraseña corregida) → VERSION 2.0.0

## Prompt issued
«Crear Roles y poder gestionarlos, en C:\Desarrollo\python\libs\doc_organize_web ya se implementado mira la decisiones
tomadas, analiza este proyecto y propón mejor estrategia — Incluir el selector de idioma para la WEB — PLAN y
AUDIT_PLAN» → «si, D1 todo en 1.24.0, D3 retirarlo, el resto según tu propuesta» → «Administrador = todo» → «2.0.0 y
reconstruye el contenedor».

## Context supplied
- doc_organize_web: ADR-013 (multi-tenant y roles), `domain/tenancy/permissions.py` y `roles.py`,
  `deps.require_permission`, sesión `2026-11-25-idioma-ingles` (2.6.0: `Me.language`, `LanguageSync`, `en-GB`,
  `Accept-Language`, D1-A).
- util_bbdd_web: `users.role` (`admin`/`user`) + `can_run_sql`/`can_apply_ddl`/`can_write_data`; `require_admin` y
  ~25 comparaciones con `role == "admin"`; i18n solo en español.
- Durante la sesión `develop` avanzó a la 1.24.0 (PR #27, idioma de los documentos, util_bbdd 5.10.0) fuera de esta
  sesión; los cambios sin confirmar se combinaron sin conflictos y se validaron juntos.

## AI output summary
- Backend:
  - `domain/identity/permissions.py` (catálogo, grupos, roles base, `LEGACY_FLAGS`) y `roles.py` (CRUD, `check_grant`,
    roles base inmutables, cierre de sesiones al quitar permisos, auditoría `role.*`).
  - `db/models.py`: `Role`; `User.role_id`, `role`, `permissions`, `can()`, `is_admin`, `sync_legacy_columns()`;
    columnas antiguas como `legacy_*`; `User.language`.
  - Migraciones `0014_roles` (roles por combinación de `can_*`, `role_id` sin `REFERENCES`, downgrade que rellena las
    columnas antiguas) y `0015_user_language`.
  - `api/deps.py`: `require_permission` y alias por permiso; routers de administración por permiso;
    `api/v1/roles.py` (nuevo); `users.py` con `role_id` y `_target()` (nadie actúa sobre quien tiene más permisos);
    preferencias con `language`; `user.can(...)` en explorador, migración, volcado, carga, jobs, conexiones y
    transferencia (`target_cannot_share`); CLI con el rol base.
  - Tests: `test_roles.py` (15, incluidas migración 0014 con datos, downgrade, escalada y preferencias de idioma),
    regla de arquitectura, `grant()` en `conftest.py` y adaptación de admin, usuarios, explorador, migración, volcado,
    carga, CLI, copia de seguridad y dominio.
- Contrato: `openapi.json` exportado y `schema.d.ts` regenerado.
- Frontend:
  - `can()`, `navigation.ts` con permiso por entrada (`allowedAdminNav`, `adminPermission`), `RequireAdmin` por ruta,
    `RolesPage.tsx`, `roleLabel.ts`, `UserFormModal`/`UsersPage` con rol, acciones ocultas sobre usuarios con más
    permisos, visores de volcado, carga y migración con `can()`.
  - i18n: `i18n/index.ts` con es/en, `useLanguageSync`, `useUpdateLanguage`, submenú «Idioma», `Accept-Language`,
    `ErrorAlert` con título por estado HTTP en inglés, `format.ts` con `intlLocale()`; `en/core.json` y
    `en/features.json` (traducción de un subagente, 1340 claves); claves `language`, `errors.http`, `admin.roles`,
    `admin.permissions`.
  - Tests: `roles.test.tsx`, `language.test.tsx`, paridad es/en y marcadores en `i18n.test.ts`, fixtures `ADMIN`/`USER`
    con rol y permisos; e2e sin activar permisos propios.
- Docs: ADR-014, `usuarios_y_sesiones.md` (roles, gestión de roles, idioma), guías con los nombres nuevos de permisos,
  glosario (inglés), `frontend.instructions.md`, CHANGELOG.
- VERSION 2.0.0 (MAJOR: la API cambia de forma incompatible): versión sincronizada en los siete sitios.
- Validaciones ejecutadas:
  - Backend: suite completa antes de combinar con la 1.24.0: 883 passed, 101 skipped, 1 fallo (revisión fijada en
    `test_backup.py`, corregido). Tras los últimos cambios y la 1.24.0: ruff, mypy, `export_openapi.py --check` y
    pytest de volcado, documentación, comparación, roles, salud, auth, copia de seguridad y arquitectura (103 passed);
    roles, admin, usuarios y transferencia (66 passed).
  - Frontend: format, lint, typecheck y build; Vitest completo con `--maxWorkers=3` (270/278: un fallo real en
    `layout.test.tsx`, corregido, y 7 tiempos agotados que pasan en serie); suites afectadas tras combinar con la
    1.24.0, 93/93.
  - `zensical build --strict` sin incidencias.
  - Docker: copia de `config.db` (revisión 0013), imagen `util_bbdd_web:2.0.0`, migraciones 0014 y 0015 aplicadas al
    arrancar, `/api/health` → `"version":"2.0.0"`, `"worker":"ok"`.
  - Navegador (8081, 2.0.0): *Administración → Roles* con los roles base y uno creado por el usuario; cambio a
    English al momento (menú, tabla y permisos traducidos) y vuelta a Español. La insignia «Base»/«Built-in» salía
    cortada en «Administrador»: corregida (`flexShrink: 0`) y la imagen reconstruida.
  - No ejecutado: Playwright.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | respuesta de la sesión (resumen en este documento) | aprobado |
| IMPLEMENT | `backend/…` · `frontend/…` · `openapi/openapi.json` · `docs/…` | completado |
| Versión | 2.0.0 | preparada, sin commit |

## Directrices para Futuras IAs
- **[permisos]**: los permisos se consultan con `user.can("…")` en el backend y `can(me, '…')` en el frontend; los
  routers usan los alias de `api/deps.py` (`UserManager`, `RoleManager`…). Un test de arquitectura prohíbe
  `role == "admin"`, `require_admin` y leer `can_*`.
- **[permisos]**: un permiso nuevo se añade a `PERMISSIONS` y `PERMISSION_GROUPS` (`domain/identity/permissions.py`),
  a `admin.permissions` de `es` y `en` (`features.json`), a `ALL_PERMISSIONS` de `frontend/src/test/api.ts` y, si
  abre una pantalla de administración, a su entrada en `app/navigation.ts`.
- **[permisos]**: cualquier endpoint que actúe sobre otro usuario debe pasar por `_target()` (`api/v1/users.py`): quien
  solo gestiona usuarios no puede actuar sobre quien tiene más permisos (restablecer la contraseña de un admin sería
  quedarse con su cuenta).
- **[bd]**: `users.role` y `users.can_*` siguen en la tabla, sin uso, escritos por `User.sync_legacy_columns()` cada
  vez que cambia el rol o sus permisos; se pueden borrar en una versión que ya no necesite volver a la 1.24.0.
- **[i18n]**: todo texto nuevo va en `src/i18n/es/` y `src/i18n/en/`; `i18n.test.ts` exige las mismas claves y
  marcadores. Los nombres de los roles base se muestran con `roleLabel()` (`roles.admin`, `roles.user`), por eso no se
  pueden renombrar.
- **[tests]**: los tests del frontend fijan el español en `test/setup.ts` (jsdom dice `en-US`); para probar en inglés,
  `setLanguage('en')` o `Me.language = 'en'`.
- **[git]**: en esta sesión `develop` y `feat/roles-idioma` avanzaron a la 1.24.0 fuera de la sesión con cambios sin
  confirmar en el árbol; comprobar la rama y `git log` antes de cerrar una versión.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commits (`feat` y `release: v2.0.0`) propuestos, no ejecutados.
- Playwright y revisión humana del inglés (estilos de Word en `templates.limits`).
- Publicación (pasos 6-8 de `docs/guides/publicar_version.md`); en el servidor, copia de seguridad antes de migrar.
