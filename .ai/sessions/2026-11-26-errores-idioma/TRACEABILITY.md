# TRACEABILITY

## Session metadata
- id: 2026-11-26-errores-idioma
- fecha: 2026-11-26
- rama: feat/errores-idioma (sobre `36822a7`, release 2.0.0 sin tag)
- skill: tech_debt + new_feature
- fase: tech_debt (solo análisis) → PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE

## Prompt issued
«Quedan pendientes huecos en la web o en la api o deudas» → `/tech-debt` (todo el repo, solo análisis, se puede
romper la API) → `/new-feature D1 errores de la API en el idioma del usuario` → catálogo en el backend **con `code`
estable** en el *problem details*; alcance: errores HTTP, 422 y `error_message`; dentro de la 2.0.0 → «sí, todo el
alcance, opción (a), adelante».

## Context supplied
- Sesión `2026-11-25-roles-idioma` (D6: título por estado HTTP, detalle en español) y `doc_organize_web`
  (`2026-11-25-idioma-ingles`, opciones D1-A/B/C).
- `core/errors.py`, `core/middleware.py`, `jobs/{context,runner,worker}.py`, `frontend/src/api/client.ts`,
  `ErrorAlert.tsx`; util_bbdd 5.10.0 (repo local): solo informes y documentos usan `_t`/`locale`.

## AI output summary
- tech_debt: veredicto `DEUDA_MENOR` (D1 errores solo en español; D2/D3 avisos de `opentelemetry-api` y `mariadb`;
  D4 Playwright fuera del CI; D5 sin auditoría de dependencias; D6 columnas `legacy_*`; D7 `check_apply` triplicado;
  D8 ramas para planes y diffs anteriores a la 1.3.0; D9 dependencias desactualizadas; D10 complejidad).
- PLAN/AUDIT_PLAN D1: `GO_CONDICIONAL` → aprobado con (a) `error_message` compuesto al leer (migración 0016).
- Infraestructura: `app/i18n/` (`Msg`, `negotiate`, `translate`, `LocalizedError`, catálogo por área), `AppError`
  con `code` y título derivados del nombre de la clase, `field_error`, `problem(code=…)` con `Content-Language` y
  `Vary`, 422 de Pydantic traducidos por `type`, `JobError(code, Msg)`, `finalize_run` guarda `error_detail`,
  `RunOut.error_message` en el idioma de quien consulta, migración `0016_run_error_detail`.
- Conversión en cuatro subagentes por área (api; identity/projects/connections/explorer/engines;
  runs/templates/uploads; jobs/integrations): 381 claves por idioma.
- Frontend: `Problem.code`, `ProblemFieldError.code`; `ErrorAlert` usa el título de la API si trae `code` y, si no
  (proxy), el de `errors.http.<status>`; `stubApi` añade `code` a los *problem details* de prueba.
- Docs: ADR-015, `usuarios_y_sesiones.md` (Idioma), CHANGELOG `[2.0.0]`, G58 en `UTIL_BBDD_GAPS.md`,
  `backend`/`api_contract.instructions.md`, `architecture.md`, `docs/README.md`, `zensical.toml`.
- Validación: ruff format/check, mypy (140 ficheros) limpios; pytest completo 904 passed (fallos por memoria en
  `test_backup`/`test_bulk` y dos reales corregidos: revisión `0016` en `test_backup` y `str(exc)` en
  `test_connections_domain`; los ficheros afectados pasan solos, 95 + 84); export OpenAPI `--check` sin cambios
  (el contrato no describe el *problem details*), `gen:api` sin diferencias; frontend format, lint, typecheck y build
  correctos; Vitest 276/280 con 2 workers: los 4 restantes son timeouts de `findBy`/5 s que fallan igual en `develop`
  sin estos cambios (equipo con 0,8 GB libres de 16); `zensical build --strict` sin avisos.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| ADR | docs/adr/ADR-015-idioma-de-los-mensajes-de-la-api.md | aceptado |
| Infraestructura | backend/app/i18n/ · backend/app/core/errors.py · backend/app/core/middleware.py | completado |
| Migración | backend/alembic/versions/0016_run_error_detail.py | completado |
| Tests | backend/tests/unit/test_i18n.py · backend/tests/api/test_errors_i18n.py · test_cli_and_migrations.py | completado |
| Frontend | frontend/src/api/client.ts · frontend/src/components/ErrorAlert.tsx · frontend/src/test/api.ts | completado |

## Directrices para Futuras IAs
- **[i18n backend]**: un error nuevo se lanza con `Msg("<área>.<situación>", **params)` y su texto va en `ES` y `EN`
  del módulo de `app/i18n/catalog/` de su área; `tests/unit/test_i18n.py` falla si falta en un idioma, si los
  marcadores difieren, si la clave no existe o si un `AppError`/`LocalizedError`/`JobError`/`errors[].msg` recibe un
  texto literal (también posicional: usar argumentos con nombre para códigos, p. ej. `PublicError(code=…, msg=…)`).
- **[i18n backend]**: el título de una subclase de `AppError` es `title.<code>`, con `code` derivado del nombre
  (`ConnectionNotFoundError` → `connection_not_found`); renombrar la clase cambia el `code` de la API.
- **[i18n backend]**: `str(exc)` de un `AppError`/`LocalizedError` es la clave, no el texto: en tests, comparar con
  `exc.detail.render("es")` o `exc.msg.render("es")`; `pytest.raises(match=…)` ya no sirve para el texto.
- **[i18n backend]**: los textos de excepciones de util_bbdd entran como parámetro (`reason`) y siguen en español
  (G58); los textos ingleses del catálogo usan comillas “…”, no «…».
- **[runs]**: `runs.error_detail` (JSON `{key, params}`) manda sobre `runs.error_message`, que solo guarda el texto en
  español para `run.json` y para las ejecuciones anteriores a la 2.0.0.
- **[frontend]**: `ErrorAlert` solo confía en `problem.title` si trae `code`; los stubs de prueba lo añaden en
  `stubApi` (`frontend/src/test/api.ts`).
- **[tests]**: con poca memoria libre, Vitest da timeouts en `runs.test`, `bulkRun.test` y `bulk.test` también en
  `develop`; repetir con `--maxWorkers=2` antes de buscar una regresión.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit `feat(backend,frontend): errores de la API en el idioma del usuario` propuesto, no ejecutado.
- Revisión humana del inglés del catálogo del backend (381 claves) junto con la del frontend.
- Playwright y publicación de la 2.0.0 (pasos 6-8 de `docs/guides/publicar_version.md`; copia de seguridad antes de
  migrar: llegan 0014, 0015 y 0016).
