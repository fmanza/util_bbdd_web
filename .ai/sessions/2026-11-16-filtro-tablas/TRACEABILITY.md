# TRACEABILITY

## Session metadata
- id: 2026-11-16-filtro-tablas
- fecha: 2026-11-16
- rama: develop
- skill: new_feature + version_closure (sesión hermana en util_bbdd: `2026-11-16-filtro-tablas-migrate-dump`)
- fase: PLAN + AUDIT_PLAN (GO_CONDICIONAL, D1/D2 resueltas) + IMPLEMENT (W-0–W-5) + VERSION → 1.19.0

## Prompt issued
«Documentación de la base de datos tiene el Filtro de tablas; lo queremos en Plan de migración DDL y en Volcado de
datos: vista previa» → D1: rutinas sin filtrar (como la documentación); D2: la lista exacta del volcado se mantiene y
es incompatible con los patrones → «implement» → «Hazlo tú» (publicar util_bbdd 5.9.0, subirla en la web, banco).

## Context supplied
- Web 1.18.0 con util_bbdd 5.8.0; filtro de la documentación de la 1.15.0 (`PatternPreview`, `tablePatterns.ts`).

## AI output summary
- `0642906` feat(runs): `table_include`/`table_exclude` en `migrate_plan` y `dump_preview` (validador común
  `normalize_filter_patterns`), `integrations/util_bbdd/table_filter.py`, `plan.json` con `filter`/`frontier`,
  vista previa con `filter`, `NoMatchingTablesError` e `invalid_params`; `PatternPreview` por operación (contexto de
  i18next: `result_migrate_plan`, `result_dump_preview`…), `TableFilterSummary` en los visores; OpenAPI y tipos.
- `f93c113` chore(backend): util_bbdd 5.9.0 (hash `a38e4e18…4e27`, lock con uv 0.12.22).
- Release 1.19.0.

## Evidencias
- Backend con el wheel 5.9.0: 814 passed, 2 skipped; ruff, mypy y `export_openapi --check` en verde.
- Frontend: 215 tests, lint, typecheck, prettier y build en verde; `zensical build --strict` limpio.
- util_bbdd: integración en el banco (migración filtrada aplicada en los 5 motores) en verde.

## Directrices para Futuras IAs
- **[runs]**: «Probar patrones» se activa por operación en `PATTERN_PREVIEW` (`LaunchRunModal.tsx`): campos de
  conexión y schema y si cuenta vistas. Textos distintos por operación: claves `<clave>_<operación>` de
  `runs.patterns` (contexto de i18next; sin ella, la de la documentación).
- **[dump]**: la vista previa comprueba antes de `plan()` que algún patrón casa; el volcado vuelve a resolver los
  patrones y `structure_hash` bloquea si cambió el conjunto de tablas.
- **[herramientas]**: el repo tiene `eol=lf`: `Path.write_text` en Windows deja CRLF y prettier lo marca; escribir
  con `write_bytes`. `uv sync --frozen` sin `--group docs` desinstala zensical del venv.

## Veredicto final
Veredicto: CLOSED — 1.19.0.
Pendientes al cierre:
- Despliegue en el servidor (lo hace el usuario, guía § 8).
