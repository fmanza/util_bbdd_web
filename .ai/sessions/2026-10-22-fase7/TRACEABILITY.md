# TRACEABILITY

## Session metadata
- id: 2026-10-22-fase7
- fecha: 2026-10-22
- rama: develop
- skill: phase
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION (Fase 7 del ROADMAP)

## Prompt issued
`/phase 7`. Respuestas: alcance completo, permiso `can_apply_ddl` + owner, escritura en el bench, `highlight.js`.
Tras AUDIT_PLAN: «IMPLEMENT, pregunta lo que necesites» → FK entre tipos distintos bloqueadas con destino
MariaDB/MySQL.

## Context supplied
- Ver `00_CONTEXT_SNAPSHOT.md`.

## AI output summary
- PLAN y AUDIT_PLAN: firmas verificadas; diseño plan → modo seco → aplicar; `GO_CONDICIONAL` con dos condiciones,
  verificadas al empezar IMPLEMENT:
  - el hash de `emit_statements()` es estable en 5 combinaciones;
  - `DatabaseOperationError` lleva el texto del driver, así que se recorta y la posición sale de la auditoría.
- Backend:
  - Migración `0006` (`users.can_apply_ddl`), API de usuarios y `Me`.
  - `integrations/util_bbdd/migrate.py`: `PlannerOptions`, `plan_to_dict` + `statements_hash`, `create_plan`,
    `apply_plan` (replanifica y compara el hash, conflictos con tablas y vistas, `validate_views`, `execute` con
    `JsonLinesAuditSink`), `fk_mismatches` (G28) y `_record_failure`.
  - `domain/runs/migrations.py`: `load_plan`, `check_plan` y `check_apply` (reglas de ADR-008), llamados desde
    `service.enqueue`. `OperationSpec.form` impide relanzar `migrate_apply`.
  - Jobs `jobs/operations/migrate.py`, con una nueva comprobación de permiso y `read_only` en el worker.
  - Endpoints `/runs/{id}/plan` y `/runs/{id}/migration-report`; tipos de artefacto `plan` y `audit`.
- Hallazgos en el bench:
  - Oracle → MariaDB generaba una FK `DOUBLE` → `INT(11)` que MariaDB rechaza a medias (G28). Se consultó al usuario
    y se bloquea con destino MariaDB/MySQL.
  - La comprobación de conflictos se amplió a vistas. Con ella se provocó un fallo a medias real para probar el
    informe.
- Frontend: `features/runs/migrate/` (`PlanViewer`, `ApplyPanel` con modal de doble confirmación,
  `MigrationReportView`, `SqlBlock` con `highlight.js` bajo demanda, `useMigrate`). El formulario oculta
  `form=false` y los grupos de otros motores destino. Se añade el interruptor *Puede aplicar DDL*.
- Tests:
  - Backend: 26 nuevos (454).
  - Integración: 12 nuevos (55) con escritura real (PostgreSQL → MySQL, MySQL → PostgreSQL, SQL Server →
    PostgreSQL, MariaDB → Oracle), hash, conflictos, FK bloqueada, fallo a medias y las 20 combinaciones.
  - Vitest: 9 nuevos (77).
  - E2E: `migrate.spec.ts` (plan → modo seco → aplicar en el bench MySQL → conflicto), con
    `tests/integration/e2e_migrate_fixture.py` antes y después.
- AUDIT_CODE (con Security Reviewer):
  - Backend local y en `backend-dev`: ruff, mypy, pytest (456) y contrato OK.
  - Integración: 56/56.
  - Frontend: format, lint, tsc, Vitest (79) y build OK; bundle principal de 492 kB.
  - Imagen 0.8.0: migración 0005 → 0006 sobre el volumen con usuarios; Playwright 28 + 2 omitidos con
    `--repeat-each=2 --workers=2`, y `migrate.spec.ts` 1/1.
  - Salidas en `build/logs/fase7_*.txt`.
- VERSION: 0.8.0, CHANGELOG, ROADMAP, ADR-008, guías (migración, usuarios, despliegue, problemas), GAPS G26–G28,
  `.ai/product.md`, sesión e `INDEX.md`.
- `/audit-code` sobre los cambios de la fase (antes del commit): APROBADO CON CONDICIONES → corregido:
  - conflictos buscados en `pg_schema` (antes, en el schema por defecto: un conflicto real pasaba el modo seco);
  - cancelar una `migrate_apply` en curso → 409 y botón oculto;
  - error de la API visible dentro del modal de confirmación;
  - `_recheck` del worker con rol owner, motor del destino y alias desaparecido como `JobError`;
  - errores de vistas saneados con `_engine_message`.
  Tests nuevos: 2 de API, 1 de integración y 2 de Vitest. Deuda registrada en ADR-008: el modo seco se asocia por
  alias y `_active_apply` no es atómico.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | conversación de la sesión | emitido (GO_CONDICIONAL, condiciones verificadas) |
| Migración Alembic | `backend/alembic/versions/0006_migrate.py` | completado |
| Capa anticorrupción | `backend/app/integrations/util_bbdd/migrate.py` | completado |
| Dominio, jobs y API | `backend/app/domain/runs/migrations.py`, `backend/app/jobs/operations/migrate.py`, `backend/app/api/v1/{runs,schemas_migrate}.py` | completado |
| Tests | `backend/tests/{unit/test_migrate_units.py,api/test_migrate.py,integration/test_bench_migrate.py,integration/e2e_migrate_fixture.py}` | completado |
| Frontend | `frontend/src/features/runs/migrate/` | completado |
| E2E | `frontend/e2e/migrate.spec.ts` | ejecutado |
| Docs | `docs/adr/ADR-008-aplicar-migraciones.md`, `docs/guides/migracion.md`, GAPS G26–G28 | completado |

## Directrices para Futuras IAs
- **[escritura-bd]**: toda operación que escriba en una BD destino (Fases 8 y 9) debe seguir ADR-008: permiso por usuario que concede un admin, rol owner, conexión no `read_only`, modo seco previo con caducidad, confirmación con el alias, comprobación al encolar **y** otra en el worker, `form=False` (no se relanza) y ninguna otra operación activa sobre el mismo destino.
- **[migrate-hash]**: `plan.json` guarda `statements_hash`. Aplicar replanifica y exige el mismo hash (G26). Si util_bbdd cambia la emisión entre versiones, los planes antiguos dejarán de aplicarse (es lo correcto: hay que replanificar).
- **[migrate-no-atomico]**: `MigrationPlan.execute` hace commit por sentencia (G27). La posición fallida y las aplicadas salen del `JsonLinesAuditSink` (evento `statement`, `attributes.position`, `message` = primera línea), nunca del texto de `DatabaseOperationError`, que trae el error del driver.
- **[fk-tipos]**: Oracle `INT`/`INTEGER` es `NUMBER` sin precisión. util_bbdd da `INT(11)` a la PK autoincremental y `number_fallback` (`DOUBLE`) a la FK (G28). `fk_mismatches` lo detecta y `fk_blocking` lo bloquea con destino MariaDB/MySQL.
- **[bench-limpieza]**: en PostgreSQL y SQL Server, un `DROP` fallido dentro de `engine.begin()` aborta la transacción (y SQL Server falla además en el COMMIT). Hay que limpiar con una sentencia por `_execute` y un try/except. Oracle → MariaDB crea los nombres en MAYÚSCULAS y MariaDB los distingue en Linux.
- **[e2e-migrate]**: `migrate.spec.ts` escribe en el bench MySQL. Necesita `UBW_E2E_MIGRATE=1`, ejecutar `python -m tests.integration.e2e_migrate_fixture setup` antes y `teardown` después, y no se ejecuta con `--repeat-each`. Los helpers de espera deben exigir una URL distinta a la de partida, porque el plan también vive en `/runs/`.
- **[heredoc]**: los scripts Python con `'''…'''`, `\n` o comillas mezcladas fallan en heredocs de bash. Hay que escribirlos con Write en el scratchpad y ejecutarlos.
- **[cancelar-escritura]**: una operación que escribe en una BD destino no se cancela en curso (`service.cancel` → 409). Al añadir volcado y carga (Fases 8 y 9), hay que decidir lo mismo o hacer la operación reanudable.
- **[bundle]**: el bundle principal está en 492 kB (aviso de Vite a 500 kB), sobre todo por `es.json`. En la Fase 8, valorar cargar i18n por ruta o dividir el JSON.

## Veredicto final
Veredicto: CLOSED (Fase 7 cumplida; DoD verificada con escritura real en 4 combinaciones de motores y E2E)
Pendientes al cierre:
- Riesgos residuales:
  - Aplicación no atómica (G27): un fallo a medias exige corrección manual.
  - Una aplicación iniciada no se puede cancelar a mitad sin dejar el destino parcial.
- El CI no ejecuta Playwright ni la integración.
- Sin commit (pendiente de petición). Siguiente paso: `/phase 8` (volcado de datos).
