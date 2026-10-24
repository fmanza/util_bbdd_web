# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versiones según
[SemVer](https://semver.org/lang/es/). Hasta 1.0, una MINOR por fase del ROADMAP.

## [Sin publicar]

### Added

- **Puesta en marcha** local y en producción (`docs/guides/puesta_en_marcha.md`), **guía de usuario**, índice
  `docs/README.md` y `.env.example`; actualizar un despliegue local sin perder los datos.
- **Sitio de documentación con Zensical**: `zensical.toml` (navegación por perfiles, anclas con tildes como en GitHub),
  grupo de dependencias `docs` en `backend/pyproject.toml` y job `docs` del CI (`zensical build --strict`).
- **Columnas en los diagramas de la documentación**: `graph_columns` (por defecto, primero las de relación y luego el
  resto; antes solo las de relación, y una tabla sin FK salía «Sin columnas visibles»), `graph_max_columns` y
  `graph_data_types`. Hueco G38 registrado: el sitio HTML omite el diagrama de las tablas sin relaciones.
- **Grafo de relaciones**: opción de columnas «Primero las de relación, luego el resto» (`column_mode=relations_first`;
  el valor por defecto sigue siendo «Solo columnas de relación»).

### Changed

- Markdown de `docs/` compatible con GitHub y con Python-Markdown: anidado a 4 espacios, línea en blanco antes de
  listas y enlaces fuera de `docs/` como URL absoluta (reglas en `docs.instructions.md`).
- La lista de comprobación de SHARED ya no trata `zensical` como término heredado de util_bbdd.

### Fixed

- **Sitio HTML de la documentación**: el panel de detalle (iframe del índice) salía bloqueado en la SPA y en «Abrir en
  pestaña nueva». CSP con `frame-src 'self'` y `frame-ancestors 'self'` solo en el índice raíz (enmienda de ADR-007).

## [1.0.0] - 2026-10-23

Fase 10 — Endurecimiento y release 1.0.

### Added

- **Revisión OWASP ASVS 4.0.3 nivel 2** con su remediación: [docs/security/ASVS_L2.md](docs/security/ASVS_L2.md)
  (capítulo por capítulo, evidencias y riesgos aceptados).
- **Cabeceras de seguridad** en toda respuesta (middleware ASGI propio): CSP de la SPA (`script-src 'self'`,
  `frame-ancestors 'none'`), `nosniff`, `Referrer-Policy`, `Permissions-Policy`, COOP/CORP, `Cache-Control: no-store`
  en `/api` y HSTS en producción con HTTPS; las CSP propias del sitio HTML y las vistas previas se respetan.
- **Rate limiting** en memoria (sin dependencias): por sesión, por IP sin sesión, intentos y fallos de login por IP y
  subidas; 429 *problem details* con `Retry-After` (`UBW_RATE_LIMIT_*`).
- **`request_id`**: cabecera `X-Request-ID` (aceptada si es válida o ULID nuevo), en cada log de la petición, en los
  *problem details* y como «Referencia» en los errores de la SPA; línea de acceso JSON propia con ruta plantilla.
- **Métricas Prometheus** en `/metrics` (`prometheus-client`), solo con el secret `ubw_metrics_token` y *bearer*:
  peticiones y latencia por ruta plantilla, 429 por regla, ejecuciones por estado y operación, latido del worker.
- **Copias de seguridad**: `python -m app.cli backup | verify-backup | restore` (instantánea en caliente de
  `config.db`, workspace y ficheros, manifiesto con SHA-256; restauración validada antes de tocar nada).
- **Guía de despliegue** tras proxy TLS (nginx y Caddy, `FORWARDED_ALLOW_IPS`, `/metrics` restringido, copias,
  variantes, prueba de carga y actualización a 1.0).
- **Prueba de carga** `scripts/load_test.py` (httpx + asyncio) con umbrales.
- **E2E**: miembros y roles, cabeceras y cookies, bloqueo de cuenta con auditoría, y vigilancia de violaciones de CSP
  en todos los specs (`e2e/fixtures.ts`).
- **Tests**: 32 nuevos (550; cabeceras, límites, métricas, copias y restauración, cookies, contraseñas comunes) en backend y 3 nuevos (105) en Vitest.

### Changed

- **util_bbdd** se instala desde la release `v4.0.0` de GitHub (mismo wheel, SHA-256 fijado en `uv.lock`); se retira
  `vendor/` (ADR-006 revisado).
- Cookies `__Host-ubw_session` y `__Host-ubw_csrf` con TLS (ASVS 3.4.4): los usuarios vuelven a iniciar sesión una vez.
- Las contraseñas nuevas se comprueban contra 45 578 contraseñas comunes (lista del NCSC, local; ASVS 2.1.7).
- `/api/openapi.json` ya no se publica en producción.
- uvicorn sin access log propio (la API escribe el suyo); `FORWARDED_ALLOW_IPS` configurable en el compose.

### Fixed

- `docs/guides/deployment.md`: el ejemplo de `printf '%s\n'` estaba partido en dos líneas.
- `frontend/src/test/api.ts` mal formateado desde la 0.10.0.

### Security

- opentelemetry-api 1.45.1 (CVE-2026-114603, ReDoS en `tracestate`) y Vite 8.3.4 (avisos del servidor de desarrollo).
- Riesgo aceptado: `mariadb` 1.1.14 (PYSEC-2026-217, sin versión corregida; no aplica con parámetros enlazados y
  `utf8mb4`).

## [0.10.0] - 2026-10-23

Fase 9 — Carga bulk.

### Added

- **Subidas** de CSV y Excel por proyecto (`POST/GET/DELETE /api/v1/projects/{id}/uploads`, `multipart/form-data`,
  migración `0008`): copia en streaming con límite de tamaño (`UBW_UPLOAD_MAX_MB`) y cuota, comprobación del contenido
  real (CSV sin NUL; `.xlsx` sin macros y con tamaño descomprimido acotado), auditoría y purga a los
  `UBW_UPLOAD_RETENTION_DAYS`. `GET …/uploads/{id}/info` devuelve columnas, muestra y hojas o separador detectado.
- **Vista previa** (`bulk_preview`, modo seco): mapeo de columnas (explícito o por nombre), validaciones (columnas
  inexistentes u obligatorias, clave primaria en update/delete), filas afectadas por PK, plan paralelo, muestra y
  **SQL generado** como artefacto (`generar_sql=True`, G35).
- **Carga** (`bulk_apply`, ADR-010): insert, update y delete con `BulkCrud`; permiso «Puede escribir datos» + owner,
  vista previa sin errores de menos de 60 min con el mismo fichero, conexión y estructura, confirmación del alias y,
  en update/delete, de las **filas afectadas** (el worker las vuelve a contar antes de escribir); plan paralelo con
  aceptación expresa de que no es atómico (G36); rechazos en `rechazos.csv`, auditoría `carga.jsonl` y filas antes y
  después (G37).
- **API**: `GET /api/v1/runs/{id}/bulk-preview` y `GET /api/v1/runs/{id}/bulk-result`.
- **Frontend**: pestaña *Carga* del proyecto (subida, asistente con mapeo y vista previa), visor de la vista previa
  con SQL y modal de confirmación, y resultado con particiones.
- **Tests**: 30 nuevos en backend (518; cargas reales SQLite en el CI), 10 de integración escribiendo en los 5
  motores del bench, 12 en Vitest (102) y E2E de subida → insertar → borrar con confirmación.
- **Documentación**: guía [Carga bulk](docs/guides/carga.md), ADR-010, huecos G35–G37, nota de proxy
  (`client_max_body_size`).

### Changed

- El permiso `can_write_data` se muestra como **«Puede escribir datos»** (antes *Puede volcar datos*): cubre volcado y
  carga.
- La cuota de usuario cuenta también los ficheros subidos.
- Migración, volcado y carga comparten la regla de una escritura por destino y la de no cancelar en curso.
- `migrate.spec.ts` se omite en las copias de `--repeat-each` (escribe en un destino compartido del bench).

### Security

- Ficheros guardados con nombre propio (`<ulid>.<ext>`), acceso por proyecto (otro proyecto → 404) y rol editor para
  subir o borrar; un fichero en uso por una carga no se borra.
- Errores de la carga con la primera línea del motor y los valores enmascarados (G34).
- `audit_log` registra en cada carga la vista previa, el fichero, el destino, la tabla, la operación y las filas
  confirmadas.

## [0.9.0] - 2026-10-23

Fase 8 — Volcado de datos.

### Added

- **Vista previa** (`dump_preview`, modo seco, solo lectura): orden de carga por FK y ciclos (el mismo que util_bbdd,
  G29), filas en origen y destino, columnas omitidas u obligatorias sin origen, FK fuera del volcado y avisos (destino
  con filas, tablas sin destino, motor sin gestión de constraints, Oracle con «apartar» G32, SQLite con fechas G33).
- **Volcado** (`dump_apply`, ADR-009): `DumpOrchestrator` con los parámetros de la vista previa; permiso
  **`can_write_data`** (migración `0007`) + owner, vista previa de menos de 60 min y con la misma estructura, destino
  no `read_only`, confirmación con el alias y «VACIAR» si se vacía el destino; sin dos volcados a la vez, sin relanzar
  ni cancelar en curso; rechazos aislados en `rechazos.csv`, informe Excel, `result.json` y auditoría.
- **API**: `GET /api/v1/runs/{id}/dump-preview` y `GET /api/v1/runs/{id}/dump-result`.
- **Frontend**: visor de la vista previa con panel de volcado y doble confirmación, resultado por tabla con constraints
  y rechazos, interruptor *Puede volcar datos*.
- **Tests**: 32 nuevos en backend (488; volcados reales SQLite → SQLite en el CI), 13 de integración escribiendo en
  los bench (69: PostgreSQL → MySQL/MariaDB, MySQL → PostgreSQL, Oracle → SQL Server y MariaDB → Oracle, con
  constraints reactivadas, rechazos y errores enmascarados), 11 en Vitest (90) y E2E de vista previa → vaciar y
  volcar → añadir.
- **Documentación**: guía [Volcado de datos](docs/guides/volcado.md), ADR-009, huecos G29–G34.

### Changed

- **Bundle**: React y el router en `vendor-react`, i18next y TanStack Query en `vendor-app`, y las traducciones de las
  pantallas (`src/i18n/es/features.json`) en un chunk que se carga con la primera ruta lazy; el chunk principal pasa
  de 492 kB a 132 kB (sin aviso de Vite). `src/i18n/es.json` se divide en `es/core.json` y `es/features.json`.
- Las escrituras en curso en la BD destino (migración y volcado) comparten la regla de no cancelación.

### Security

- Los mensajes de error del volcado se guardan sin los parámetros de SQLAlchemy (que traen filas del origen) y con
  los valores de clave enmascarados (MySQL/MariaDB, SQL Server; G34).
- Auditoría de código previa al cierre: la vista previa guarda el id de las conexiones y un alias reasignado no
  vale; migración y volcado no pueden escribir a la vez en el mismo destino; `audit_log` detalla cada volcado;
  `work/` se borra aunque util_bbdd falle; el patrón de tablas ya no admite `schema.tabla`; un test estático
  impide usar claves de pantallas fuera de las rutas lazy.

## [0.8.0] - 2026-10-22

Fase 7 — Migración DDL.

### Added

- **Plan de migración** (`migrate_plan`): `MigrationPlanner` de util_bbdd entre Oracle, MariaDB, MySQL, SQL Server y
  PostgreSQL (origen ≠ destino), con las opciones del planner por motor destino; guarda `plan.json` (tablas, tipos,
  avisos, sentencias y su SHA-256) y el script SQL. Solo lee el origen.
- **Aplicar** (`migrate_apply`, ADR-008): modo seco obligatorio (mismo hash del plan, conflictos con tablas y vistas
  del destino, validación de vistas, FK entre tipos distintos) y aplicación con `MigrationPlan.execute` y auditoría
  por sentencia (`outputs/audit/migracion.jsonl`); informe con la sentencia fallida y las aplicadas.
- Permiso **`can_apply_ddl`** (migración `0006`, administración de usuarios, `Me`) + rol owner; destino no
  `read_only` y del motor del plan; modo seco de menos de 60 min; confirmación con el alias; sin dos aplicaciones a
  la vez sobre el mismo destino; `migrate_apply` no se relanza ni sale en el formulario genérico (`form=false`).
- **API**: `GET /api/v1/runs/{id}/plan` y `GET /api/v1/runs/{id}/migration-report`; `OperationOut.form`.
- **Frontend**: visor del plan (avisos por severidad, mapeo de tipos, sentencias con `highlight.js` 11.12.0 cargado
  bajo demanda), panel *Aplicar* con modo seco, historial y modal de doble confirmación; informe de la aplicación;
  formulario con solo las opciones del motor destino; interruptor *Puede aplicar DDL*.
- **Tests**: 28 nuevos en backend (456), 13 de integración **escribiendo** en los bench (56: aplicación real en cuatro
  combinaciones, hash, conflictos también en `pg_schema`, fallo a medias real, las 20 combinaciones planificables),
  11 en Vitest (79) y E2E de plan → modo seco → aplicar contra el bench.
- **Documentación**: guía [Migración DDL](docs/guides/migracion.md), ADR-008, huecos G26–G28.

### Security

- Toda escritura en BD destino exige permiso + owner, conexión no `read_only`, modo seco y confirmación, y se vuelve
  a comprobar en el worker; errores del motor recortados y sin URL de conexión.
- Las FK entre tipos distintos que MariaDB/MySQL rechazarían bloquean la aplicación (G28).
- Auditoría de código previa al cierre: los conflictos se buscan en `pg_schema` con destino PostgreSQL; una
  aplicación en curso no se cancela (409); el worker vuelve a comprobar también rol owner y motor del destino; los
  errores de validación de vistas se recortan como los del motor; el error al aplicar se ve dentro del modal.

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
