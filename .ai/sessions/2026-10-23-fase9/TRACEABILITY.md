# TRACEABILITY

## Session metadata
- id: 2026-10-23-fase9
- fecha: 2026-10-23
- rama: develop
- skill: phase
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION (Fase 9 del ROADMAP)

## Prompt issued
`/phase 9`. Respuestas: reutilizar `can_write_data`, insert/update/delete con confirmación de filas, `multipart`,
alcance completo. Tras AUDIT_PLAN: «IMPLEMENT, pregunta lo que necesites».

## Context supplied
- Ver `00_CONTEXT_SNAPSHOT.md`.

## AI output summary
- PLAN y AUDIT_PLAN: `GO_CONDICIONAL` con tres condiciones, verificadas en el bench al empezar:
  - formato del SQL generado;
  - `generar_sql=True` (valor por defecto, G35) no escribe en ninguno de los 5 motores;
  - el recuento de filas afectadas por lotes de PK es exacto.
- Backend:
  - Dependencia `python-multipart`; ajustes `UBW_UPLOAD_MAX_MB`, `UBW_UPLOAD_MAX_UNCOMPRESSED_MB`,
    `UBW_UPLOAD_RETENTION_DAYS` y `UBW_BULK_MAX_ROWS`; migración `0008` (`uploads`).
  - `domain/uploads/` (copia en streaming con límites y cuota, contenido real, lectura CSV/Excel, purga, auditoría)
    y router `api/v1/uploads.py`.
  - `integrations/util_bbdd/bulk.py`: recibe un `DataFrame` (no importa `app.domain`), mapeo, validaciones,
    `_count_matches` deduplicado, `structure_hash`, `build_bulk_preview` y `run_bulk`.
  - `domain/runs/bulks.py` (`check_preview`, `check_apply`) y jobs `jobs/operations/bulk.py`.
  - `bulk_apply` se añade a `WRITE_OPERATIONS` y a `NOT_CANCELLABLE_RUNNING`.
  - Endpoints `/bulk-preview` y `/bulk-result`.
  - El permiso pasa a llamarse «Puede escribir datos».
- Hallazgo: `rows_committed`/`last_operation_rows_committed` no son fiables (G37). El resultado lo calcula la web
  (filas antes y después). Un paralelo de más de un hilo no es atómico (G36): se exige `accept_non_atomic`.
- Frontend:
  - Pestaña *Carga* del proyecto (`features/bulk/`), con subida, mapeo con desplegables de la tabla (consulta con
    retardo) y vista previa.
  - `features/runs/bulk/`: `BulkPreviewViewer` con SQL y modal de confirmación (alias, filas, no atómico) y
    `BulkResultView`.
- AUDIT_CODE:
  - Mejora añadida: el worker vuelve a contar las filas afectadas antes de escribir y aborta con `preview_changed`
    si no son las confirmadas. Test incluido.
  - La pestaña no estaba en `TABS` de `ProjectDetailPage`: lo detectó Vitest.
  - `migrate.spec.ts` se omite en las copias de `--repeat-each` (escribe en un destino compartido del bench), igual
    que dump y bulk.
  - Backend local y en `backend-dev`: 518 tests (+30), ruff, mypy y contrato OK.
  - Integración de carga en los 5 motores del bench: 10/10.
  - Frontend: format, lint, tsc, Vitest 102 (+12) y build OK.
  - Imagen 0.10.0: migración 0007 → 0008; Playwright 31 + 3 omitidos con `--repeat-each=2 --workers=2`, migración
    incluida.
  - Salidas en `build/logs/fase9_*.txt`.
- VERSION: 0.10.0, CHANGELOG, ROADMAP, ADR-010, guías (carga nueva; usuarios, volcado, despliegue, problemas,
  proyectos), arquitectura, GAPS G35–G37, README, `.ai/product.md`, sesión e `INDEX.md`.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | conversación de la sesión | emitido (GO_CONDICIONAL, condiciones verificadas) |
| Migración Alembic | `backend/alembic/versions/0008_uploads.py` | completado |
| Subidas | `backend/app/domain/uploads/`, `backend/app/api/v1/uploads.py` | completado |
| Capa anticorrupción | `backend/app/integrations/util_bbdd/bulk.py` | completado |
| Dominio, jobs y API | `backend/app/domain/runs/bulks.py`, `backend/app/jobs/operations/bulk.py`, `backend/app/api/v1/{runs,schemas_bulk}.py` | completado |
| Tests | `backend/tests/{unit/test_bulk_units.py,api/test_bulk.py,integration/test_bench_bulk.py}` | completado |
| Frontend | `frontend/src/features/bulk/`, `frontend/src/features/runs/bulk/` | completado |
| E2E | `frontend/e2e/bulk.spec.ts` | ejecutado |
| Docs | `docs/adr/ADR-010-carga-bulk.md`, `docs/guides/carga.md`, GAPS G35–G37 | completado |

## Directrices para Futuras IAs
- **[bulk-generar-sql]**: `BulkCrud.bulk_*_from_df` tiene `generar_sql=True` por defecto (G35) y entonces **no ejecuta**. Hay que pasarlo siempre explícito: `True` con `path_sql` en la vista previa y `False` al cargar.
- **[bulk-contadores]**: `rows_committed`/`last_operation_rows_committed` no son fiables (G37); `rows_rejected` sí. Las filas afectadas se calculan con `_count_matches` (claves deduplicadas antes de partir en lotes) y con recuentos antes y después.
- **[bulk-capas]**: el fichero lo lee el dominio (`domain/uploads/files.read_frame`) y la integración recibe un `DataFrame`. `integrations/` no puede importar `app.domain` (test de arquitectura).
- **[bulk-confirmacion]**: en update/delete, `confirm_rows` debe ser igual a `matches` de la vista previa al encolar, y el worker vuelve a contar antes de escribir (`MatchesChangedError` → `preview_changed`). Cualquier operación nueva que borre o cambie filas existentes debería seguir el mismo patrón.
- **[subidas]**: los ficheros se guardan como `<ulid>.<ext>` en `users/{owner}/projects/{id}/uploads/`, nunca con el nombre del usuario. Cuentan en `usage_bytes` y se purgan con `purge_old_uploads` salvo que los use una carga. Un proxy delante necesita `client_max_body_size` ≥ `UBW_UPLOAD_MAX_MB`.
- **[e2e-escritura]**: los specs que escriben en un destino compartido (dump, bulk, migrate) se omiten con `repeatEachIndex > 0`. `bulk.spec.ts` necesita `e2e-carga.db` (esquema de `volcado_vacio.sql`) en `/data/files`, reescrita como `app`.
- **[bench-puertos]**: el contenedor `util_bbdd_bench_mssql` publica 1433 en el puerto 51833, no en el 51433 por defecto de los tests. Hay que exportar `UTIL_BBDD_BENCH_MSSQL_PORT=51833` (`docker port util_bbdd_bench_mssql`).
- **[heredoc-escapes]**: en esta sesión el Bash tool convirtió `\n` y `\u0000` dentro de heredocs en caracteres reales. Los scripts con escapes hay que escribirlos con Write.
- **[i18n]**: `ProjectDetailPage` valida la pestaña pedida contra `TABS`. Una pestaña nueva debe añadirse allí; si no, cae en *Ejecuciones* sin error.

## Veredicto final
Veredicto: CLOSED (Fase 9 completa; DoD verificada con escritura real en 5 motores, SQLite en el CI y E2E)
Pendientes al cierre:
- Riesgos residuales:
  - Los ficheros subidos, el SQL generado y `rechazos.csv` contienen datos de negocio visibles para los miembros.
  - Una carga paralela fallida deja particiones confirmadas (G36, con aceptación expresa).
  - Las limitaciones G32 y G34 aplican también a la carga.
- El CI no ejecuta Playwright ni la integración.
- Sin commit (pendiente de petición). Siguiente paso: `/phase 10` (endurecimiento y release 1.0).
