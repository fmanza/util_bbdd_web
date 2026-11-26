# TRACEABILITY

## Session metadata
- id: 2026-11-26-deuda-2.2.0
- fecha: 2026-11-26
- rama: chore/deuda-2.2.0 (sobre `37dd5ed`, merge del refactor D7)
- versión: 2.2.0 (incluye D7 de `[Unreleased]`)
- skill: tech_debt (seguimiento) → plan + implement
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE

## Prompt issued
«Algo pendiente de la deuda» → «Hazlo todo» → alcance: escaneo de la imagen, aviso de httpx, D6 + D8, bench en el CI
+ D10; una sola versión al final → AUDIT_PLAN `GO_CONDICIONAL` → «sí, adelante con IMPLEMENT».
Fuera por decisión: revisión humana del inglés, excepción de mariadb (2027-02-26) y D9 (Dependabot).

## Context supplied
- Trivy 0.76.1 sobre `util_bbdd_web:2.1.1`: 12 HIGH/CRITICAL con arreglo, todas de Debian (openssl, perl, pcre2, apt).
- `starlette.testclient` avisa si usa `httpx`; `httpx2` 2.16.0 (2026-10-21).
- `users.role` con `ck_users_role` (CHECK): SQLite no permite `DROP COLUMN`; 13 tablas apuntan a `users` (CASCADE o
  SET NULL); `env.py` migraba con el engine de la app (`foreign_keys=ON`) dentro de una transacción.
- D8: `replan()` y la rama del job para planes sin `migration_plan.json` (1.3.0); `LEGACY_DIFF_FORMAT` (1.2.0).
- D10 (ruff C901 > 11): `update_user`, `enqueue`, `bulk._prepare` (12); `run_bulk` con 58 sentencias.

## AI output summary
- Imagen: `PYTHON_IMAGE` 3.12.15-slim-bookworm (de 12 a 4 hallazgos); Trivy (imagen Docker, no la action) en el job
  `image` con `--ignore-unfixed --exit-code 1`; `.trivyignore` con CVE-2026-84782 (DTLS, no se usa) y
  CVE-2026-109518 (apt, solo al construir), revisión 2026-12-26. Escaneo local de la imagen nueva: código 0.
- httpx → `httpx2>=2.16.0` (dev) y `scripts/load_test.py`; sin avisos en pytest.
- D6: `alembic/env.py` fija `foreign_keys=OFF` antes de la transacción, exige `foreign_key_check` vacío y devuelve la
  conexión con `foreign_keys=ON`; migración `0017` recrea `users` sin `role`/`can_*` (la bajada las repone con
  `ADD COLUMN` desde el rol). Fuera `legacy_*`, `sync_legacy_columns`, `LegacyRole`, `LEGACY_FLAGS`. Test de la 0017
  desde la 0013 (pasa por la DML de la 0014) contando filas hijas en las dos direcciones.
- D8: `migrate_apply` rechaza planes sin `migration_plan.json` al encolar (`runs.migrate.plan_too_old`) y en el worker
  (`jobs.migrate.plan_too_old`); fuera `replan()` y la clave `jobs.migrate.source_changed`. `read_diff` ya no lee el
  formato 1 (el visor responde 404 como con un diff dañado).
- Bench en el CI: `docker run` de `postgres:17.11` y `mysql:8.4.11` en el job `e2e` (55432/53306, contraseña de un solo
  uso), `docker/compose.e2e.yml` (`host.docker.internal:host-gateway`), `UBW_E2E_MIGRATE=1` y
  `e2e_migrate_fixture setup` con uv.
- D10: `_check_operation` sale de `enqueue`; `run_bulk` en `_bulk_crud` + `_load`; ruff C901 (máx. 12) y PLR0915 en
  `app/` (tests y migraciones fuera).
- Docs: `onboarding_dev.md` (bench local, Trivy y excepciones), `deployment.md` (0017, vuelta atrás), SHARED,
  `backend.instructions.md` (migraciones con `foreign_keys=OFF`), ASVS 14.2.1, CHANGELOG `[2.2.0]`, versión 2.2.0.
- Validación local: tests afectados (179 + 136 de D7) en verde; `migrate.spec` + `connections.spec` con el bench local
  (puertos 15432/13306 por las reservas de Hyper-V): 5 passed; 0017 sobre una copia de la base local (2 usuarios,
  36 auditorías, 1 proyecto…): mismas filas en las 18 tablas, `foreign_key_check` vacío, bajada a 0016 correcta.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Migración | backend/alembic/versions/0017_drop_legacy_user_columns.py · backend/alembic/env.py | completado |
| CI | .github/workflows/ci.yml · .trivyignore · docker/compose.e2e.yml · docker/Dockerfile | completado |
| D8 | backend/app/{domain/runs/migrations,jobs/operations/migrate,integrations/util_bbdd/{migrate,compare}}.py | completado |
| D10 | backend/app/domain/runs/service.py · backend/app/integrations/util_bbdd/bulk.py · backend/pyproject.toml | completado |

## Directrices para Futuras IAs
- **[migraciones]**: `alembic/env.py` migra con `foreign_keys=OFF` (fijado antes de la transacción: SQLite ignora el
  PRAGMA dentro de una) y falla si `foreign_key_check` no sale vacío; una migración que recrea una tabla lo comprueba
  (`PRAGMA foreign_keys` = 0) y su test cuenta filas hijas desde una revisión anterior a una migración con DML.
- **[migraciones]**: los tests que siembran `users` con SQL directo lo hacen en una revisión concreta (`0016` si
  usan `role`); desde la 0017 `users` no tiene `role` ni `can_*`.
- **[imagen]**: subir `PYTHON_IMAGE` con versión exacta de ≥ 2 semanas y quitar de `.trivyignore` lo que corrija;
  Trivy se ejecuta como imagen Docker con versión fija, no con `aquasecurity/trivy-action`.
- **[e2e]**: el bench del CI publica 55432/53306 en el runner; en Windows (Hyper-V) usar otros puertos con
  `UTIL_BBDD_BENCH_*_PORT` y `COMPOSE_FILE` separado por `;`.
- **[complejidad]**: ruff C901 (máx. 12) y PLR0915 vigilan `backend/app`; `update_user` y `bulk._prepare` están en el
  límite.

## Veredicto final
Veredicto: CLOSED (2.2.0) — AUDIT_PLAN `GO_CONDICIONAL` → `GO`: la 0017 conserva todas las filas hijas (test y copia
de la base local) y el CI pasa con los jobs nuevos.
- pytest completo: 912 passed, 101 skipped, sin avisos.
- PR #31 (run 45891176321): `e2e` 24 passed y 0 skipped (bench PostgreSQL + MySQL en el runner Linux con
  `host-gateway`), `image` con Trivy sin hallazgos fuera de `.trivyignore`; fusionado en `develop` (`791a022`, run
  45895784165 en verde) y rama borrada.
Pendientes al cierre:
- Commit `release: v2.2.0 - deuda técnica (Trivy, columnas antiguas, bench en la E2E)` propuesto, no ejecutado.
- Publicación (pasos 6-8 de `docs/guides/publicar_version.md`) con copia de seguridad antes: llega la `0017`.
- Revisar `.trivyignore` el 2026-12-26 y `PYSEC-2026-217` el 2027-02-26; revisión humana del inglés.
- Ideas no comprometidas: bench con MariaDB/SQL Server/Oracle y `pytest -m integration` en el CI; regla de tamaño
  para los componentes del frontend.
