# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versiones según
[SemVer](https://semver.org/lang/es/). Hasta 1.0, una MINOR por fase del ROADMAP.

## [0.3.0] - 2026-10-20

Fase 2 — Catálogo de motores y conexiones.

### Added

- **Catálogo de motores** (`GET /api/v1/engines`, `GET /engines/{db_type}`): los 7 motores de util_bbdd con
  versiones, puerto, drivers (y si están instalados en el servidor), características, parámetros de conexión
  clasificados (secreto, destino, ruta, bloqueado) y matriz de capacidades verificadas: async, migración origen y
  destino, readiness (GAPS G4/G5).
- **Conexiones** (`/api/v1/connections`): CRUD con visibilidad privada o compartida (solo admin), `read_only` por
  defecto, contraseña cifrada con MultiFernet (ADR-004) que nunca se devuelve; validación de parámetros contra el
  catálogo y con `build_conn_params` de util_bbdd; rutas confinadas en `UBW_FILES_DIR`; `init_command` bloqueado.
- **Prueba de conexión y readiness** (`POST /connections/{id}/test`, `GET /connections/{id}/readiness`) en un
  subproceso con timeout (`UBW_CONNECTION_TEST_TIMEOUT`), máximo 4 simultáneas (429), errores saneados con código
  estable; `last_test_*` en la conexión.
- **Allowlist anti-SSRF** (`/api/v1/admin/allowlist`): deniega por defecto; CIDR, IP, host o `*.dominio`;
  link-local, multicast y reservadas siempre denegadas; loopback solo con red explícita.
- **CLI** `python -m app.cli rotate-secrets`.
- **Frontend**: catálogo con matriz y ficha, lista y detalle de conexiones (prueba, readiness, borrado con
  confirmación), formulario dinámico generado desde la ficha del motor con React Hook Form + Zod (*resolver* propio),
  administración de destinos permitidos; secciones *Motores* y *Conexiones* habilitadas.
- **Tests**: 78 nuevos en backend (151 en total) más 11 de integración contra los contenedores bench de util_bbdd
  (PostgreSQL, MySQL, MariaDB, SQL Server, Oracle; `-m integration`); 20 nuevos en Vitest (39); E2E de catálogo,
  conexiones, allowlist y prueba real contra el bench PostgreSQL desde el contenedor.
- **Documentación**: guía [Motores y conexiones](docs/guides/conexiones.md); destinos y ficheros en despliegue;
  notas de implementación en ADR-004; huecos G10–G16 en `UTIL_BBDD_GAPS.md`.

### Changed

- La API no arranca en producción sin `ubw_fernet_keys` (además de `ubw_app_secret_key`).
- La imagen fija `UBW_FILES_DIR=/data/files` y el *entrypoint* crea la carpeta.
- Los *problem details* de errores de dominio pueden llevar `errors` por campo (como los 422 de validación).

### Dependencias

- Python: `cryptography` como dependencia directa (50.0.2, ya presente como transitiva).
- npm: `react-hook-form` 7.89.0 y `zod` 4.6.5 (este ya estaba como transitiva de desarrollo), publicadas antes del
  corte de 2026-10-05.

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
