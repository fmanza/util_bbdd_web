# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versiones según
[SemVer](https://semver.org/lang/es/). Hasta 1.0, una MINOR por fase del ROADMAP.

## [0.2.0] - 2026-10-20

Fase 1 — Identidad y multiusuario.

### Added

- **Backend**: modelos `users`, `sessions` y `audit_log` con migración Alembic `0002` (con `downgrade`);
  contraseñas Argon2id (`pwdlib`) con política mínima; sesión de servidor en cookie `ubw_session`
  (`HttpOnly; Secure; SameSite=Lax`) con rotación al iniciar sesión y caducidad por inactividad y absoluta; en BD solo
  el SHA-256 del token; CSRF de doble envío firmado (`ubw_csrf` + `X-CSRF-Token`, HMAC ligado a la sesión) en todo
  método no seguro de `/api/v1`; bloqueo temporal tras intentos fallidos; auditoría de autenticación y
  administración; CLI `python -m app.cli create-admin`.
- **API**: `GET /api/v1/auth/csrf`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `POST /auth/password`;
  `/api/v1/users` (listar, crear, ver, editar, desactivar/reactivar, restablecer contraseña); `GET` y `DELETE`
  `/api/v1/sessions`; `GET /api/v1/audit`. Solo `admin` en usuarios, sesiones y auditoría (`403` para `user`).
- **Frontend**: pantalla de login, guardas de ruta (`RequireAuth`, `RequireAdmin`), menú de usuario, cambio de
  contraseña, administración de usuarios, sesiones (revocación con confirmación) y auditoría con filtro; páginas de
  administración con carga diferida; cabecera CSRF automática en el cliente.
- **Ajustes**: `UBW_SESSION_IDLE_MINUTES`, `UBW_SESSION_ABSOLUTE_HOURS`, `UBW_LOGIN_MAX_ATTEMPTS`,
  `UBW_LOGIN_LOCKOUT_MINUTES`, `UBW_PASSWORD_MIN_LENGTH`.
- **Tests**: 61 nuevos en backend (73 en total), 16 nuevos en Vitest (19), E2E de login y administración con
  Playwright.
- **Documentación**: guía [Usuarios, sesiones y auditoría](docs/guides/usuarios_y_sesiones.md); primer
  administrador en despliegue, incorporación y README; notas de implementación en ADR-003.

### Changed

- La SPA exige sesión: `/` redirige a `/login` sin ella; `/api/health` sigue siendo público.
- `ubw_app_secret_key` es obligatorio en producción: sin él la API no arranca.
- `alembic.ini` declara `path_separator = os` (aviso de deprecación de Alembic).

### Dependencias

- Python: `pwdlib[argon2]` 0.3.1 (con `argon2-cffi`).

## [0.1.0] - 2026-10-19

Fase 0 — Fundaciones.

### Added

- **Backend**: FastAPI con fábrica `create_app`, `/api/health` (estado de `config.db` y versiones), errores
  `application/problem+json` (RFC 9457), logging JSON, ajustes `UBW_*` y Docker secrets, SQLite con WAL y
  `foreign_keys`, Alembic (revisión vacía `0001`), capa anticorrupción `integrations/util_bbdd` con test de
  arquitectura, worker esqueleto, export de OpenAPI con `--check`.
- **Frontend**: Vite + React + TypeScript estricto, Mantine, TanStack Query, React Router, i18n en español,
  cliente tipado generado desde OpenAPI, layout con navegación por fases, página de inicio con el estado del
  servicio, 404 de la SPA, tests con Vitest y E2E de humo con Playwright.
- **Docker**: imagen multi-stage (`runtime`, `backend-dev`), variantes `WITH_HSQLDB` / `WITH_ODBC`, compose con
  `web` y `worker` (perfil), volúmenes `data` y `workspace`, secretos, usuario no root, `read_only`, `cap_drop`.
- **CI**: backend (ruff, mypy, pytest, contrato OpenAPI), frontend (prettier, eslint, tsc, vitest, cliente al día,
  build) e imagen con arranque y `/api/health`; Dependabot con *cooldown* de 14 días.
- **Documentación**: ROADMAP de 11 fases, `UTIL_BBDD_GAPS.md` (G1–G9), ADR-001…006, arquitectura, guías de
  incorporación, despliegue y solución de problemas.
- **Configuración IA**: `SHARED_INSTRUCTIONS.md`, `CLAUDE.md`, `copilot-instructions.md`, 8 instrucciones por ruta,
  11 agentes (nuevo: Frontend Reviewer), 9 prompts (nuevo: `phase_implementation`), 9 slash commands (nuevo:
  `/phase`), hooks de Claude Code.

### Dependencias

- util_bbdd 4.0.0 vendorizado; Python resuelto con `exclude-newer = 2026-10-05` (excepción: asyncpg);
  npm instalado con `--before=2026-10-05`.
