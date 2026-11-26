# TRACEABILITY

## Session metadata
- id: 2026-11-26-ci-e2e-audit
- fecha: 2026-11-26
- rama: feat/ci-e2e-audit (sobre `73a15c1`, release 2.1.0)
- versión: 2.1.1
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE

## Prompt issued
`/new-feature D4+D5, todo lo queremos en una unica versión` (deuda del inventario de `2026-11-26-errores-idioma`) →
auditoría bloqueante con excepciones (dev de npm solo avisa), E2E completa salvo el bench, en push, PR y cada lunes,
versión 2.1.1 → «sí, adelante con IMPLEMENT».

## Context supplied
- `.github/workflows/ci.yml`, `frontend/playwright.config.ts`, `frontend/e2e/*.spec.ts` (requisitos en sus cabeceras),
  `docs/guides/onboarding_dev.md` (§ E2E completa), `backend/app/cli.py` (`create-admin --password-stdin`),
  `docs/security/ASVS_L2.md` (14.2.1 y riesgo aceptado de `mariadb`).
- util_bbdd (solo lectura): `connection/mariadb/connection_mariadb.py` descarta `charset` al conectar
  (`_UNSUPPORTED_BY_CONNECTOR`) y el pool también.

## AI output summary
- Auditoría inicial: pip-audit con 3 hallazgos (certifi PYSEC-2026-4320, opentelemetry-api GHSA-mf5v-w3w3-f6cg,
  mariadb PYSEC-2026-217 sin versión corregida); npm de producción limpio, de desarrollo 10 (undici vía jsdom;
  minimatch vía eslint/typescript-eslint, con arreglo de menos de 2 semanas).
- CI: `schedule` (lunes 06:00 UTC) y `workflow_dispatch`; job `audit` (`pip-audit==2.10.1` sobre `uv export`,
  `--ignore-vuln PYSEC-2026-217`; `npm audit --omit=dev`; `npm audit` completo con `continue-on-error`); job `e2e`
  (imagen con caché GHA, compose con límites altos, contraseña aleatoria enmascarada, `scripts/e2e_prepare.sh`,
  Playwright con 2 workers, informe y logs como artefacto si falla).
- `scripts/e2e_prepare.sh` (nuevo): admin E2E y 5 BD SQLite de los fixtures en `/data/files`; repetible.
- Dependencias: certifi 2026.10.23, opentelemetry-api 1.45.2 (`uv lock --upgrade-package`), undici 8.12.4
  (`npm update --before=2026-11-12`). Tras ellas: pip-audit limpio (1 ignorada), npm de producción 0, dev 9 moderadas.
- Specs desfasados desde la 2.0.0: `locale: 'es-ES'` en `playwright.config.ts` (sin sesión la SPA sigue el idioma del
  navegador y Chromium usa en-US); `members.spec` usa el combobox con sugerencias; `documentation.spec` espera el
  encabezado del detalle antes de «Correcta».
- Docs: `onboarding_dev.md` (E2E con el script e instancia aparte; nueva § Auditoría de dependencias con la tabla de
  excepciones), `publicar_version.md`, `SHARED_INSTRUCTIONS.md` (Dependencias, Estrategia de tests), `ASVS_L2.md`
  14.2.1, CHANGELOG `[2.1.1]`, versión sincronizada.
- Validación: ruff format/check, mypy (140) limpios; pytest completo 910 passed, 101 skipped; `export_openapi --check`;
  frontend format, lint, typecheck y build correctos; Vitest 278/280 con 2 workers (2 timeouts de 5 s por memoria,
  0,9 GB libres; esos dos ficheros pasan solos, 15/15); `zensical build --strict` sin avisos; YAML del CI válido.
  E2E local contra la imagen 2.1.0 en una instancia aparte (`ubw-e2e`, puerto 8082): suite completa con 1 worker
  21 passed, 2 skipped (bench), 1 fallo de `compare` por un plazo de 5 s con pytest en paralelo (pasó en la pasada
  anterior); los dos specs corregidos pasan. No se ha visto aún el CI con los jobs nuevos.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| CI | .github/workflows/ci.yml | completado (sin ejecutar en GitHub) |
| Script | scripts/e2e_prepare.sh | completado |
| E2E | frontend/playwright.config.ts · frontend/e2e/members.spec.ts · frontend/e2e/documentation.spec.ts | completado |
| Locks | backend/uv.lock · frontend/package-lock.json | completado |

## Directrices para Futuras IAs
- **[e2e]**: Playwright navega con `locale: 'es-ES'` y los specs buscan textos en español; un texto nuevo de la UI que
  use un spec se busca con su traducción española.
- **[e2e]**: `scripts/e2e_prepare.sh` prepara cualquier compose levantado (CI y local); para no tocar la instancia
  local, `COMPOSE_PROJECT_NAME=ubw-e2e UBW_PORT=8082` y `UBW_E2E_URL=http://127.0.0.1:8082`.
- **[e2e]**: en este equipo (≈1 GB libre) los inicios de sesión y los jobs van lentos con 2 workers; con fallos por
  plazo, repetir con `--workers=1` antes de tocar un spec.
- **[auditoría]**: una excepción de `pip-audit` lleva `--ignore-vuln` en `ci.yml`, fila en la tabla de
  `onboarding_dev.md` § Auditoría de dependencias (motivo y fecha de revisión) y riesgo aceptado en `ASVS_L2.md`.
- **[auditoría]**: `pip-audit` no cubre util_bbdd (dependencia por URL) ni los paquetes del sistema de la imagen.

## Veredicto final
Veredicto: pendiente de AUDIT_CODE y del primer CI con los jobs nuevos.
