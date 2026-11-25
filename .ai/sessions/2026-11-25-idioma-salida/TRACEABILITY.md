# TRACEABILITY

## Session metadata
- id: 2026-11-25-idioma-salida
- fecha: 2026-11-25
- rama: feature/util-bbdd-5.10-locale (desde `develop` en `dbc8259`; PR #27, fusionada en `556aa16` y borrada)
- skill: new_feature + version_closure
- fase: PLAN + AUDIT_PLAN (en la sesión de util_bbdd 5.10.0, fases W1 y W2) → IMPLEMENT → VERSION 1.24.0

## Prompt issued
«Analiza tambien el impacto en util_bbdd_web» → «PLAN y AUDIT_PLAN por fases» (en la sesión de i18n de util_bbdd)
→ «haz W1 y W2 en util_bbdd_web» → «haz los commits, push y abre la PR a develop» → «revisa el CI de la PR» → «haz el
merge de la PR a develop» → «haz el cierre de versión 1.24.0 en util_bbdd_web y elimina la rama
feature/util-bbdd-5.10-locale cuando no la necesites».

## Context supplied
- util_bbdd 5.10.0 publicada (tag `v5.10.0`, wheel y `.sha256`): parámetro `locale` (`"es"` por defecto, `"en"`) en
  `DatabaseDocumentation`, `SchemaDiffReporter` (keyword-only) y `DumpConfig`; excepciones, logs y nombres de columna
  de las hojas de auditoría fuera de alcance.
- Plan W1 (subir util_bbdd + parámetro Idioma en documentación, comparación y volcado) y W2 (`lang` del visor
  Markdown); la interfaz de la web no se traduce.
- `docs/guides/publicar_version.md` y `.github/instructions/sync.instructions.md`.

## AI output summary
- W1:
  - `backend/pyproject.toml` + `uv.lock` a util_bbdd 5.10.0 con uv 0.12.22 (la de `UV_IMAGE`); hash del lock igual al
    `.sha256` de la release. Versión esperada en `test_health.py`/`test_runs.py`, ADR-006, `architecture.md` y
    `publicar_version.md`.
  - `domain/runs/operations.py`: `OutputLocale = Literal["es", "en"]` y `_locale()` (grupo `output`, defecto `es`) en
    `DocumentationParams`, `CompareParams` y `DumpPreviewParams`.
  - `integrations/util_bbdd/{documentation,compare,dump}.py`: campo `locale` en las opciones y paso a util_bbdd;
    `jobs/operations/{compare,dump}.py` pasan `params.locale` (documentación lo recibe vía `model_dump`).
  - Frontend: `launchLayout.ts` (tarjetas *Formatos*, *Informes*, *Carga y errores*) e i18n `features.json`
    (`runs.groups.output`, `runs.params.*.locale`, `runs.options.es/en`).
- W2: `markdownFrame.ts` (`FrameLang`, `frameLang()`, parámetro `lang` de `buildFrameDocument`), `MarkdownViewer.tsx`
  y `DocumentationOutputs.tsx` (`lang={frameLang(run.params.locale)}`).
- Tests: `test_documentation.py` (+3: catálogo, `fr` → 422, Excel `Columns`), `test_compare.py` (+1: `lang="en"`, hoja
  `Summary`, diff sin cambios), `test_dump.py` (+1: hoja `Table Audit`), `markdownNav.test.ts` (+1).
- Docs: guías `documentacion.md`, `comparacion.md`, `volcado.md`; CHANGELOG.
- Commits `ce7e645` (`chore(backend): util_bbdd 5.10.0`) y `dba9780` (`feat: idioma de los documentos e informes
  (locale)`); PR #27 con CI verde (backend, frontend, docs, image) y fusionada en `develop` (`556aa16`); rama borrada
  en local y en el remoto tras el merge.
- VERSION 1.24.0: CHANGELOG, `pyproject.toml`, `__init__.py`, `package.json`/`package-lock.json`, `uv.lock`
  (uv 0.12.22), `openapi.json` (`info.version`) y `.env.example` (`UBW_TAG`); `schema.d.ts` sin cambios.
- Validaciones ejecutadas:
  - Antes de la PR: backend pytest 870 passed / 101 skipped, ruff, format, mypy, `uv lock --check --offline`,
    `export_openapi.py --check`; frontend 267 tests con `--maxWorkers=2`, lint, typecheck, prettier, build;
    `zensical build --strict`.
  - CI de la PR #27 en verde.
  - Con 1.24.0: `export_openapi.py --check` OK; pytest `test_health`, `test_runs`, `test_auth` (52 passed);
    `zensical build --strict` sin incidencias; imagen `util_bbdd_web:1.24.0` (`docker build --target runtime`) y
    `docker compose up -d --no-build` en 8081 → `/api/health` `"version":"1.24.0"`, `"util_bbdd_version":"5.10.0"`,
    `"worker":"ok"`.
  - No ejecutados: Playwright; prueba manual en navegador de una ejecución en inglés.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | sesión de util_bbdd `.ai/sessions/2026-11-25-i18n-resultados/` (W1/W2) | aprobado |
| IMPLEMENT | `backend/…` · `frontend/…` · `docs/…` · `CHANGELOG.md` | completado (`ce7e645`, `dba9780`, PR #27) |
| Versión | 1.24.0 | preparada, sin commit |

## Directrices para Futuras IAs
- **[backend]**: el idioma de las salidas es un parámetro de la operación (`locale`, grupo `output`), no una
  preferencia de usuario; las ejecuciones anteriores sin `locale` se validan con el defecto `es`. `dump_apply` no lo
  declara: usa el `DumpConfig` de su vista previa.
- **[frontend]**: el `lang` del iframe del visor Markdown pasa siempre por `frameLang()`; no interpolar
  `run.params.locale` directamente en el HTML del documento.
- **[tests]**: las salidas en inglés se comprueban por los nombres de hoja de `xl/workbook.xml` del Excel (`Columns`,
  `Summary`, `Table Audit`), que no dependen de los datos.
- **[versión]**: `uv lock` con `uvx --from uv==0.12.22 uv lock` para no cambiar el formato del lock con el uv local
  (0.13.1).
- **[tests]**: Vitest con el paralelismo por defecto da timeouts en suites no tocadas (administración, carga) también
  en la rama base; usar `--maxWorkers=2` para comparar.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit `release: v1.24.0 - idioma de los documentos e informes (util_bbdd 5.10.0)` propuesto, no ejecutado.
- Push de `develop`, CI, `main` (fast-forward), tag `v1.24.0`, release de GitHub y despliegue
  (`docs/guides/publicar_version.md`, pasos 6-8).
- Contenedores locales (8081) en 1.24.0.
