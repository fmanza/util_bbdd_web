# ROADMAP — util_bbdd_web

Plan por fases para exponer toda la funcionalidad de util_bbdd 4.0.0 en una aplicación web multiusuario. Cada fase
se implementa con `/phase <n>` (prompt `phase_implementation`) y se cierra con una versión MINOR (`0.<n+1>.0`).

Orden: de **solo lectura** a **escritura en BD**, para que los controles (roles, `read_only`, confirmaciones,
auditoría) estén probados antes de las operaciones destructivas.

| Fase | Nombre | Versión | Estado |
|---|---|---|---|
| 0 | Fundaciones | 0.1.0 | ✅ Cerrada (2026-10-19) |
| 1 | Identidad y multiusuario | 0.2.0 | ✅ Cerrada (2026-10-20) |
| 2 | Catálogo de motores y conexiones | 0.3.0 | ✅ Cerrada (2026-10-20) |
| 3 | Proyectos y motor de ejecuciones | 0.4.0 | ✅ Cerrada (2026-10-22) |
| 4 | Explorador de metadatos | 0.5.0 | ✅ Cerrada (2026-10-22) |
| 5 | Documentación y grafos | 0.6.0 | ✅ Cerrada (2026-10-22) |
| 6 | Comparación de esquemas | 0.7.0 | ✅ Cerrada (2026-10-22) |
| 7 | Migración DDL | 0.8.0 | ✅ Cerrada (2026-10-22) |
| 8 | Volcado de datos | 0.9.0 | ✅ Cerrada (2026-10-23) |
| 9 | Carga bulk | 0.10.0 | ✅ Cerrada (2026-10-23) |
| 10 | Endurecimiento y release | 1.0.0 | Pendiente |

**DoD común a todas las fases**: comandos de desarrollo en verde (backend y frontend), OpenAPI exportado y cliente
regenerado, migración Alembic con `downgrade`, tests de autorización (401/404), imagen construida y `/api/health`
200, CHANGELOG, documentación de usuario de lo implementado y `TRACEABILITY.md` de la sesión.

---

## Fase 0 — Fundaciones ✅

- Estructura backend (FastAPI) y frontend (Vite + React + TS), capa anticorrupción con util_bbdd.
- `/api/health`, errores RFC 9457, logging JSON, SQLite con WAL, Alembic (revisión vacía `0001`).
- Docker multi-stage (`runtime`, `backend-dev`), compose con `web` y `worker` (perfil), secretos, endurecimiento.
- Cliente OpenAPI generado, layout con navegación por fases, i18n en español.
- CI (backend, frontend, imagen + health), Dependabot con *cooldown* de 14 días.
- Configuración IA (Claude Code + Copilot), ADR-001…006, este ROADMAP y `UTIL_BBDD_GAPS.md`.

## Fase 1 — Identidad y multiusuario ✅

**Historias**
- Como admin, creo, desactivo y reactivo usuarios y asigno el rol `admin` o `user`.
- Como usuario, inicio y cierro sesión, y cambio mi contraseña.
- Como admin, veo y revoco sesiones activas, y consulto el registro de auditoría.

**Backend**: modelos `users`, `sessions`, `audit_log`; `pwdlib[argon2]`; cookie de sesión + CSRF (ADR-003);
bloqueo por intentos; comando `python -m app.cli create-admin`; dependencia `current_user` / `require_admin`.
**Endpoints**: `POST /api/v1/auth/login`, `POST /auth/logout`, `GET /auth/me`, `POST /auth/password`,
`/api/v1/users` (CRUD admin), `/api/v1/sessions` (admin), `GET /api/v1/audit` (admin).
**Frontend**: pantalla de login, guardas de ruta, menú de usuario, administración de usuarios y sesiones.
**Tests**: hash y verificación, bloqueo, CSRF obligatorio, cookie con flags, IDOR, E2E de login.

## Fase 2 — Catálogo de motores y conexiones ✅

**Historias**
- Veo la ficha de cada motor: nombre, descripción, rango de versiones, puerto por defecto, drivers (y si están
  instalados), características, soporte async, operaciones disponibles (p. ej. migración) y parámetros de conexión.
- Creo conexiones con un formulario generado desde los `connection_params` del motor, las pruebo y veo su informe
  de readiness.
- Como admin, creo conexiones compartidas (otros las usan sin ver el secreto) y gestiono la allowlist de destinos.

**util_bbdd**: `SyncDatabaseManager.get_supported_db_types()`, `get_db_type_info_static(db_type)`,
`database_types.json` (vía la capa anticorrupción), `core.capabilities.is_async_supported`,
`connection.build_conn_params`, `get_database_info()`, `get_engine_readiness()`.
**Backend**: modelo `connections` con `secret_enc` (Fernet, ADR-004), `visibility`, `read_only`; allowlist; prueba
de conexión en el worker o con timeout corto; saneado de errores.
**Endpoints**: `GET /api/v1/engines`, `GET /engines/{db_type}`, `/api/v1/connections` (CRUD),
`POST /connections/{id}/test`, `GET /connections/{id}/readiness`, `/api/v1/admin/allowlist`.
**Frontend**: catálogo de motores con matriz de capacidades, formulario dinámico (RHF + Zod generado), detalle de
conexión con prueba y readiness.
**Mejora incluida**: matriz de capacidades por motor y operación construida en la capa anticorrupción (GAPS G4/G5).

## Fase 3 — Proyectos y motor de ejecuciones ✅

**Historias**
- Creo proyectos, invito miembros (`owner`/`editor`/`viewer`) y asocio conexiones con alias (`origen`, `destino`).
- Lanzo una ejecución y sigo su progreso; la cancelo.
- Veo el historial de ejecuciones del proyecto **agrupado por ejecución** (operación, usuario, estado, duración,
  artefactos), filtro y busco; abro cada artefacto (vista previa HTML/Markdown/SVG/SQL) y descargo el ZIP.
- Relanzo una ejecución con los mismos parámetros.

**Backend**: `projects`, `project_members`, `project_connections`, `runs`, `artifacts`; cola de jobs y worker con un
subproceso por job (ADR-002); SSE `GET /api/v1/runs/{id}/events`; workspace (ADR-005) con `run.json`, `run.log`,
`outputs/<formato>/`; `RunAuditSink` (implementa `util_bbdd.audit.AuditSink`); retención y cuotas.
Job de prueba `noop` para validar el motor antes de las operaciones reales.
**Frontend**: lista y detalle de proyecto, miembros, conexiones del proyecto, historial de ejecuciones, detalle de
ejecución con progreso en vivo (`aria-live`), navegador de artefactos con vistas previas en `iframe sandbox`.

## Fase 4 — Explorador de metadatos ✅

**util_bbdd**: `get_schema_metadata(schema, *, kinds, tables) -> SchemaSnapshot`, `metadata_source`,
`metadata/ddl.py`, `get_available_queries()`, `execute_query_many/one()`, `execute_custom_many/one()`.
**Funcionalidad**: árbol schema → tablas/vistas/rutinas; detalle de tabla (columnas, claves, índices, FK, DDL);
ejecutor de queries nombradas; SQL libre solo para rol autorizado, sobre conexión `read_only`, con timeout y límite
de filas; caché del snapshot por conexión con invalidación manual.

## Fase 5 — Documentación y grafos ✅

**util_bbdd**: `DatabaseDocumentation(db_manager, directorio_salida, fichero_salida=…, imprimir, formatos,
batch_window_seconds=0).generate()`; `GraphvizRelationshipGraphExt` (`generate_graphviz_graph_paginated_ext`,
`generate_all_tables_graphs_ext`).
**Funcionalidad**: ejecución `documentation` (Word/Excel/HTML, opciones de `imprimir`), ejecución
`relationship_graph` (tabla o todas, profundidad, dirección, columnas, SVG/PNG); sitio HTML navegable aislado
(ADR-007), descargas y galería de grafos en la web.

## Fase 6 — Comparación de esquemas ✅

**util_bbdd**: `SchemaComparator().compare(source: Inspector, target: Inspector, *, source_schema, target_schema,
include_tables, include_views, include_indices, include_foreign_keys, include_comments, include_routines)` →
`SchemaDiff`; `SchemaDiffReporter(...).render(diff, output_dir, format)` / `render_all`.
**Funcionalidad**: ejecución `compare` entre dos conexiones o schemas; visor del diff navegable; descargas SQL,
HTML, Word, Excel y Markdown. **Mejora opcional** (incluida): comparar dos ejecuciones `compare` en fechas distintas
(nuevas, resueltas y persistentes).

## Fase 7 — Migración DDL ✅

**util_bbdd**: `MigrationPlanner(source_engine, target_engine, charset, collation, number_fallback, engine,
int_display_width, sql_server_collation, pg_schema, oracle_identity_mode, view_strategy).plan(connection, schema)`
→ `MigrationPlan` (`emit_ddl()`, `emit_statements()`, `warnings`, `execute(target_connection, *, audit_sink)`).
**Funcionalidad**: ejecución `migrate_plan` (scripts por motor destino + avisos); visor del plan; ejecución separada
`migrate_apply` con doble confirmación, conexión destino no `read_only` y rol autorizado. Solo combinaciones
soportadas (oracle, mariadb, mysql, sqlserver, postgresql; origen ≠ destino). Hecho según ADR-008: permiso
`can_apply_ddl` + owner, modo seco obligatorio (hash del plan, conflictos, vistas y FK entre tipos distintos).

## Fase 8 — Volcado de datos ✅

**util_bbdd**: `DumpOrchestrator(DumpConfig(source_engine, target_engine, source_schema, target_schema, tables,
chunk_size, output_dir, truncate_target, manage_indexes, max_parallel_tables, on_error, audit_sink, …)).run()` →
`DumpResult` (`report`, `load_order`, `cycles_detected`, `table_results`…).
**Funcionalidad**: vista previa del orden de carga por FK y ciclos (modo seco); ejecución `dump` con confirmación;
informe Excel y resumen por tabla. `truncate_target` desactivado por defecto en la UI. Hecho según ADR-009: permiso
`can_write_data` + owner, vista previa obligatoria (60 min, misma estructura), «VACIAR» para vaciar, rechazos
aislados; además, bundle repartido (vendors y traducciones de pantallas en chunks propios).

## Fase 9 — Carga bulk ✅

**util_bbdd**: `BulkCrud(engine, *, batch, audit, rejects, execution, parallel)` con
`bulk_insert/update/delete_from_df` y `_from_chunks`, `maintenance_scope(...)`, `parallel_plan(...)`.
**Funcionalidad**: subida CSV/Excel validada (tamaño, tipo, columnas), mapeo de columnas, vista previa,
insert/update/delete con plan paralelo, SQL generado como artefacto, rechazos y auditoría. Hecho según ADR-010:
subidas `multipart` con contenido verificado, vista previa con filas afectadas y SQL (`generar_sql=True`, G35),
permiso `can_write_data` + owner, confirmación del alias y, en update/delete, de las filas afectadas; paralelo
opcional con aceptación de que no es atómico (G36).

## Fase 10 — Endurecimiento y release 1.0

- Revisión OWASP ASVS nivel 2 (`/security-review` completo) y remediación.
- Cabeceras de seguridad, rate limiting de login y API, métricas Prometheus, logs JSON con `request_id`.
- Backup y restauración de `config.db` (`sqlite3 .backup`) y del workspace; guía de despliegue tras proxy TLS.
- E2E de todos los flujos; prueba de carga básica; imagen variante HSQLDB/ODBC verificada.
- Publicación de util_bbdd en un índice privado o GitHub Releases y retirada del wheel vendorizado (ADR-006).

## Mejoras opcionales (fuera de fase, decidir al planificar)

- Plantillas de ejecución por proyecto.
- Ejecuciones programadas (cron por proyecto), después de la 1.0.
- Tokens de API personales para lanzar ejecuciones desde CI.
- Notificaciones al terminar una ejecución larga.
- Migración de `config.db` a PostgreSQL si crece la concurrencia (solo URL de SQLAlchemy + Alembic).
