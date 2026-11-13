# TRACEABILITY

## Session metadata
- id: 2026-11-13-zensical-toml
- fecha: 2026-11-13
- rama: develop
- skill: new_feature + version_closure (sesión hermana en util_bbdd: `2026-11-13-zensical-only`)
- fase: PLAN + AUDIT_PLAN (GO_CONDICIONAL) + IMPLEMENT (W-12.0–W-12.2) + AUDIT_CODE + VERSION → 1.16.0

## Prompt issued
`/new-feature`: subir util_bbdd de 5.5.0 a 5.6.0 y adaptar la web a que la documentación Markdown genera
`zensical.toml` en lugar de `mkdocs.yml` (G55). Decisiones aprobadas: adaptar a `zensical.toml` (no pasar
`markdown.mkdocs_yml`) y subir zensical del grupo `docs` a `>=0.1.1,<0.2` con excepción de `exclude-newer`.
Después `/version-closure 1.16.0` y despliegue según `publicar_version.md`.

## Context supplied
- Código de la web 1.15.0; util_bbdd 5.6.0 (tag `v5.6.0`, `f2ac916e`; `_site.zensical_toml`, CHANGELOG [5.6.0]).

## AI output summary
- `d21f80b` chore(backend): util_bbdd 5.6.0 (hash del lock = `.sha256` de la release, `6a42e09e…`; uv 0.12.22).
  Los 3 tests que esperaban `mkdocs.yml` se adaptan aquí (ajuste respecto del PLAN, para no dejar la suite en rojo).
- `52f29cd` feat: textos de la tarjeta Markdown y del aviso del README, test del frontend, comentarios y descripción
  del parámetro `markdown` (no está en OpenAPI); `zensical>=0.1.1,<0.2` con excepción fechada para `zensical` y
  `zensical-ui` (2026-11-10).
- `1d5d0f3` docs: guía, enmienda de ADR-007, G55 resuelto, W-12 en `UTIL_BBDD_GAPS_PLAN.md`, CHANGELOG.
- AUDIT_CODE (en la conversación): APROBADO; sin cambios de lógica ni del contrato HTTP.

## Evidencias
- Backend `pytest -m "not integration"` (sin `UTIL_BBDD_BENCH_PASSWORD`): 801 passed, 2 skipped; ruff, mypy y
  `export_openapi.py --check` en verde (`build/logs/w12_pytest.txt`).
- Frontend: format, lint, typecheck, 203/203 tests y build (`build/logs/w12_frontend.txt`).
- `zensical build --strict` del sitio de la web con Zensical 0.1.1: sin avisos.
- Prueba real en una instancia local aislada (API + worker con uv, puerto 8099): documentación Markdown generada por
  la API, ZIP con `zensical.toml` (`extra_javascript` local, `font = false`) y `mermaid.min.js`;
  `zensical build --strict` del ZIP sin avisos; abierta en Chromium bloqueando todo lo que no fuera 127.0.0.1, el
  diagrama ER se dibuja y no hubo ninguna petición externa.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| util_bbdd 5.6.0 | `d21f80b` | completado |
| zensical.toml en la web | `52f29cd` | completado |
| Documentación y G55 | `1d5d0f3` | completado |
| Release | `release: v1.16.0` | ver Veredicto final |

## Directrices para Futuras IAs
- **[backend/integración]**: desde util_bbdd 5.6.0 la configuración del sitio Markdown es `zensical.toml`; la web no
  pasa `markdown.mkdocs_yml` (en desuso, se retira en 6.0.0). Ningún código depende del nombre del fichero: el ZIP
  añade el Mermaid por `MARKDOWN_MERMAID_ARTIFACT` y `run.json` → `markdown_mermaid`.
- **[backend/dependencias]**: el 2026-11-13 se adelantó `exclude-newer` a `2026-11-11T00:00:00Z` (decisión explícita
  del usuario, excepción a la regla de 2 semanas) y se retiró `exclude-newer-package` entero (asyncpg,
  opentelemetry-api, zensical, zensical-ui). Hasta el 2026-11-25 no ejecutes `uv lock --upgrade` sin revisar lo que
  entra. Al subir zensical, `zensical-ui` va con versión exacta.
- **[pruebas/Markdown]**: el tema de Zensical dibuja Mermaid dentro de un shadow DOM: `.mermaid svg` no lo encuentra
  un selector normal; para comprobar los diagramas usa una captura o el contenido del shadow root.
- **[pruebas/manual]**: para una prueba real sin tocar la instancia Docker en uso, levanta API y worker con
  `uv run` y `UBW_ENVIRONMENT=development` (cookies sin `__Host-`), `UBW_DATA_DIR`/`UBW_WORKSPACE_DIR` temporales,
  `alembic upgrade head` y `python -m app.cli create-admin --password-stdin`.

## Veredicto final
Veredicto: CLOSED (1.16.0)
Pendientes al cierre: ver la sección Handoff de la conversación (push, CI, `main`, tag y despliegue).
