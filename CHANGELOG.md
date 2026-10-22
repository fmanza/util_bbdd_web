# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versiones según
[SemVer](https://semver.org/lang/es/). Hasta 1.0, una MINOR por fase del ROADMAP.

## [0.7.0] - 2026-10-22

Fase 6 — Comparación de esquemas.

### Added

- **Comparación** (`compare`): `SchemaComparator` de util_bbdd entre dos conexiones del proyecto (o dos schemas),
  con selección de tablas, índices, FK, comentarios, vistas y rutinas; schema comprobado por lado (también en Oracle,
  donde SQLAlchemy normaliza los nombres) y errores que indican el lado (origen/destino).
- Diff guardado como artefacto (`outputs/diff/schema_diff.json`, tipo `diff`) e informes HTML, Excel, Word, Markdown y
  SQL con `SchemaDiffReporter` (dialecto automático según el destino). El script SQL solo se genera.
- **API**: `GET /api/v1/runs/{id}/diff` (diff tipado; 413 por encima de 20 MB) y
  `GET /api/v1/runs/{id}/diff/evolution?baseline=` (diferencias nuevas, resueltas y persistentes entre dos
  comparaciones, con aviso si origen o destino difieren).
- **Frontend**: visor del diff (resumen, pestañas, filtros por nombre y estado, detalle de tablas, definiciones de
  vistas y rutinas lado a lado con `diff` 9.0.0 cargado bajo demanda), panel *Comparar con otra ejecución*, tarjeta
  de informes con el HTML aislado y aviso del script SQL.
- **Tests**: 28 nuevos en backend (428; dos SQLite reales, sin rutas del servidor en ningún artefacto), 6 de
  integración contra los bench (43; los 5 motores y PostgreSQL contra MySQL), 5 en Vitest (68) y E2E de comparación
  y evolución.
- **Documentación**: guía [Comparación de esquemas](docs/guides/comparacion.md), huecos G23–G25.

### Security

- Las etiquetas de util_bbdd (host, usuario, ruta del SQLite) se sustituyen por `alias (motor) [schema]` en el diff y
  en todos los informes (G23).
- El informe HTML no carga Mermaid del CDN: se sustituye por un `mermaid` vacío local para que su script funcione
  bajo la CSP aislada (G25).

## [0.6.0] - 2026-10-22

Fase 5 — Documentación y grafos.

### Added

- **Documentación** (`documentation`): ejecución de `DatabaseDocumentation` de util_bbdd en Word, Excel y/o sitio
  HTML, con las secciones de `imprimir` agrupadas en el formulario (tablas, vistas, rutinas, información adicional,
  diagramas y presentación) y schema por motor (GAPS G22). Oracle solo admite el schema del usuario de la conexión
  (G21, con aviso en el formulario).
- **Grafo de relaciones** (`relationship_graph`): `GraphvizRelationshipGraphExt` sobre una tabla (paginado) o sobre
  todas las tablas con relaciones; profundidad, dirección, columnas, tipos y SVG/PNG.
- **Sitio HTML aislado** (ADR-007): `GET /api/v1/runs/{id}/site/{token}/{ruta}` con URL firmada y temporal
  (`site_url` en el detalle), CSP `sandbox allow-scripts` sin `allow-same-origin`, `connect-src 'none'` y solo
  artefactos `html` registrados.
- Catálogo de operaciones: los parámetros incluyen `options` (desplegables) y `group` (secciones del formulario).
- `schema` y `table` solo admiten nombres de objeto (letras, dígitos, `_ $ # . -` y espacios): util_bbdd puede
  usarlos en el SQL de sus consultas de catálogo.
- **Frontend**: formulario por secciones con desplegables; tarjeta *Documentación* (sitio en `iframe` con scripts y
  origen opaco, abrir en pestaña nueva, descargas de Word y Excel); galería de grafos; Markdown renderizado con
  `marked` 18.1.0 (cargado bajo demanda) en un `iframe` sin permisos; los ficheros del sitio no se listan.
- Graphviz en el job de backend del CI y en la imagen `backend-dev`.
- **Tests**: 43 nuevos en backend (400; util_bbdd real sobre SQLite: los 3 formatos, grafos, URL firmada, tokens
  caducados o ajenos, *traversal*), 11 de integración contra los bench (37), 3 en Vitest (63) y E2E de documentación
  (aislamiento del sitio comprobado en Chromium) y grafo.
- **Documentación**: guía [Documentación y grafos](docs/guides/documentacion.md), ADR-007, huecos G21–G22.

### Fixed

- La vista previa de un PNG de `outputs/graphs/` se servía como `text/html`; ahora usa su tipo MIME.

### Changed

- Los selectores de operación y de conexión del formulario de lanzamiento son `select` nativos.

## [0.5.0] - 2026-10-22

Fase 4 — Explorador de metadatos.

### Added

- **Explorador** (`/api/v1/connections/{id}/metadata/…`) para cualquier conexión visible: schemas (con los del
  sistema marcados), árbol de tablas, vistas y rutinas desde `get_schema_metadata`, detalle de tabla (columnas, PK,
  únicas, checks, índices, FK salientes y entrantes) y DDL con `util_bbdd.metadata.ddl`; snapshot cacheado y comprimido
  por conexión y schema (`metadata_cache`) con refresco manual e invalidación al editar la conexión.
- **Queries nombradas**: CRUD de administradores (`/api/v1/admin/queries`, plantillas `{param}` de util_bbdd validadas
  como de solo lectura) y ejecución desde el explorador con `resolve_query` de util_bbdd; los parámetros solo admiten
  identificadores o números (GAPS G18).
- **SQL libre** (`/api/v1/projects/{id}/connections/{alias}/sql`): permiso por usuario `can_run_sql` (lo activa un
  admin), rol editor, conexión `read_only`, guardián `sqlglot` (una única consulta de lectura, sin DML/DDL/`INTO`/
  bloqueos/comandos en ningún nodo), transacción de solo lectura del motor (PostgreSQL, MySQL, MariaDB, Oracle,
  SQLite; SQL Server con aviso), `ROLLBACK`, límite de filas y timeout; mensaje del motor recortado; auditoría con el
  texto de la consulta.
- Ejecutor genérico de tareas de util_bbdd en subproceso con timeout (`isolated.py`); la prueba de conexión lo usa.
- **Frontend**: explorador (`/connections/:id/explore`) con árbol filtrable, detalle por pestañas y queries
  nombradas; pestaña *SQL* del proyecto; administración de queries; interruptor del permiso en *Usuarios*.
- **Tests**: 161 nuevos en backend (357; guardián con 147 casos), 15 de integración contra los bench (26), 8 en Vitest
  (60) y E2E del explorador, queries y SQL libre sobre SQLite.
- **Documentación**: guía [Explorador y SQL](docs/guides/explorador.md); usuarios de BD de solo lectura en
  despliegue; huecos G17–G20.

### Fixed

- Detalle de ejecución: si el evento SSE `run` terminal llegaba antes que `end`, la fuente se cerraba y los artefactos
  no aparecían hasta recargar (la detectó el E2E con carga).
- E2E de la Fase 2: la entrada `host.docker.internal` de la allowlist ya no se quita al terminar (copias en paralelo).

### Changed

- `Me` y `UserOut` incluyen `can_run_sql`; migración `0005` con `server_default` para los usuarios existentes.

### Dependencias

- Python: `sqlglot` como dependencia directa (30.21.0, ya presente como transitiva de util_bbdd).

## [0.4.0] - 2026-10-22

Fase 3 — Proyectos y motor de ejecuciones.

### Added

- **Proyectos** (`/api/v1/projects`): miembros con rol `owner`/`editor`/`viewer` (siempre al menos un owner; se
  puede salir), conexiones asociadas por alias (solo propias o compartidas; los miembros las usan sin ver el
  secreto). Quien no es miembro recibe 404.
- **Motor de ejecuciones** (ADR-002): cola propia sobre `runs` con reclamación atómica `UPDATE … RETURNING`, worker
  (`python -m app.jobs.worker`) con un subproceso *spawn* por job, latidos, cancelación (termina el subproceso),
  timeout, detección de hijos caídos, recuperación de huérfanos y parada limpia con SIGTERM.
- **API de ejecuciones**: lanzar (202), historial agrupado por ejecución con filtros y búsqueda, `GET /runs` de mis
  proyectos, progreso en vivo por SSE (`/runs/{id}/events`), cancelar, relanzar, purgar, descarga y vista previa de
  artefactos (CSP `sandbox`), ZIP en *streaming*; catálogo `GET /operations`.
- **Workspace** (ADR-005): carpeta por ejecución con `run.json`, `logs/run.log` y `outputs/<formato>/`, rutas solo con
  IDs, artefactos con SHA-256, retención por días y por proyecto, cuota por usuario y límite de cola.
- `RunAuditSink` (implementa `util_bbdd.audit.AuditSink`, sin `message`) para las fases 7–9.
- Job `noop` con pasos, fallo simulado, prueba de una conexión del proyecto y artefactos de ejemplo.
- `/api/health` informa `worker: ok|stale|absent`.
- **Frontend**: proyectos (lista, alta, detalle con pestañas de ejecuciones, conexiones, miembros y ajustes según el
  rol), lanzamiento con formulario generado desde la operación, detalle de ejecución con progreso en vivo
  (`aria-live`, sondeo de reserva), cancelar, relanzar, purgar, navegador de artefactos con vista previa en
  `iframe sandbox` y descarga del ZIP; sección *Ejecuciones*.
- **Tests**: 45 nuevos en backend (196 en total; el worker se prueba con subprocesos reales en el CI), 13 nuevos en
  Vitest (52) y E2E de proyecto → ejecución → artefactos → ZIP → relanzar, y de cancelación.
- **Documentación**: guía [Proyectos y ejecuciones](docs/guides/proyectos_y_ejecuciones.md); notas de
  implementación en ADR-002 y ADR-005; variables nuevas en arquitectura; solución de problemas.

### Changed

- `docker compose up` arranca también el `worker` (ya no es un perfil) con `stop_grace_period: 30s`; el CI espera a
  `"worker": "ok"`.
- El worker usa `signal.signal` (multiplataforma) en lugar de `signal.sigwait`: `mypy` pasa también en Windows.
- Test de arquitectura ampliado a las dependencias entre capas (`workspace`, `domain`, `api`, `integrations`).
- Vitest: `asyncUtilTimeout` de Testing Library a 3 s (suite completa en paralelo).

### Dependencias

- Ninguna nueva (SSE nativo de FastAPI 0.142, ULID propio, `zipfile`).

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
