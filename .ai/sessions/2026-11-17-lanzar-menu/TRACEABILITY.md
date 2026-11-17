# TRACEABILITY

## Session metadata
- id: 2026-11-17-lanzar-menu
- fecha: 2026-11-17
- rama: develop
- skill: new_feature + version_closure
- fase: PLAN + AUDIT_PLAN (GO_CONDICIONAL; D2 `requires` en backend, D4 `noop` visible al final) + IMPLEMENT +
  AUDIT_CODE (propio) + VERSION → 1.20.0

## Prompt issued
«Ampliar las ventanas de "Lanzar ejecución", más anchas, reorganizar las tarjetas (crear nuevas si hace falta) y
reorganizar el menú de la izquierda» → modal ancho, menú Propuesta 1 con iconos (dependencia nueva aceptada) →
«IMPLEMENT» → `/version-closure` y actualizar el contenedor local.

## Context supplied
- Web 1.19.0; formulario genérico generado de `GET /api/v1/operations` (grupos `ubw_group`, `ubw_requires`).

## AI output summary
- Backend: `requires` en `tables_per_document` (word), `html_items_per_page` (html), `sql_dialect` (sql) e
  `indexes`/`foreign_keys`/`comments` (tables; verificado en util_bbdd: solo cuentan con `include_tables`).
- Frontend: `features/runs/launch/` (`launchLayout.ts`, `LaunchForm.tsx`, `LaunchCard.tsx`, `OperationRail.tsx`,
  `DumpTableSelection.tsx`, `dumpMode.ts`, `grid.ts`); `LaunchRunModal.tsx` como estructura del modal;
  `app/navigation.ts` + `Layout.tsx` (secciones, administración plegable, hamburguesa); `@tabler/icons-react` 3.50.0.
- Tests: `launch.test.tsx`, `app/layout.test.tsx`, helper `test/launch.ts`; 6 tests y 7 specs E2E adaptados.
- Docs: guías de proyectos y ejecuciones, usuario, documentación, comparación, migración, volcado y usuarios.

## Evidencias
- Backend: 910 passed, 12 skipped; ruff, mypy y `export_openapi --check` en verde.
- Frontend: 226 tests, lint, typecheck, prettier y build en verde; `zensical build --strict` limpio.
- E2E: no ejecutados en la sesión de implementación.

## Directrices para Futuras IAs
- **[runs]**: la distribución del formulario «Lanzar ejecución» vive en `features/runs/launch/launchLayout.ts`
  (`LAUNCH_LAYOUTS`); un parámetro del backend sin tarjeta cae en «Otros», nunca se pierde. Un parámetro nuevo de
  una operación existente hay que colocarlo ahí.
- **[runs]**: `PATTERN_PREVIEW`, `ENGINE_GROUPS` y `ORACLE_SOURCE_PARAMS` están ahora en `launch/LaunchForm.tsx`;
  `DISABLED_WITHOUT` (desactivar, se envía) y `SHOWN_WHEN` (ocultar por valor, no se envía) en `launchLayout.ts`.
- **[runs]**: los tests eligen la operación con `chooseOperation(user, dialog, título)` (`src/test/launch.ts`); el
  modal preselecciona la primera de `OPERATION_CATEGORIES` (documentación), no `noop`.
- **[dump]**: el filtro del volcado tiene modo Todas / Lista exacta / Patrones (`dumpMode.ts`); los tests y E2E que
  rellenen patrones deben elegir antes «Patrones».
- **[frontend]**: el menú se define en `app/navigation.ts` (claves de `core.json`, bundle inicial); la sección de
  administración guarda su estado en `localStorage` (`ubw.nav.adminOpened`) y está siempre abierta en `/admin/*`.

## Veredicto final
Veredicto: CLOSED — 1.20.0 (commit propuesto, no ejecutado).
Pendientes al cierre:
- E2E de Playwright contra `docker compose up` (specs adaptados sin ejecutar).
- Revisión visual del modal (ancho, pie fijo, modo oscuro) y del menú en móvil.
- Publicar (push, tag) y desplegar en el servidor: los hace el usuario (guía § 6–8).
