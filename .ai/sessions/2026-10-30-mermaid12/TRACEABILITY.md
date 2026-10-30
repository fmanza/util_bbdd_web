# TRACEABILITY

## Session metadata
- id: 2026-10-30-mermaid12
- fecha: 2026-10-30
- rama: develop
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION (sin commit ni release)

## Prompt issued
1. «En el "Informes de la comparación" dice "Mermaid no disponible: diagrama en texto", en el diagrama de diferencia
   en HTML, tampoco se visualiza en comparacion.md. Mermaid tiene que ser version 12 o superior. Dame opciones».
2. Elegidas las opciones 1 (Mermaid incrustado en el HTML) + A (diagramas del Markdown dibujados en la SPA);
   `/new-feature`; plan aprobado («si»).
3. Levantar el bench PostgreSQL para la E2E de conexiones; subir `chunkSizeWarningLimit` en Vite.

## Context supplied
- ADR-007 (sitio HTML aislado, CSP), GAPS G25 (`mermaid_src=None`), `compare.py` de la integración.
- util_bbdd 5.1.0 en el repo origen (solo lectura): `HtmlDiffReporter(mermaid_src: str | Path | None)` incrusta un
  `Path` en `<script>`; la plantilla usa `mermaid.initialize` y `mermaid.run({nodes, suppressErrors})`;
  `MERMAID_VERSION = "10.9.8"`.
- npm: `mermaid@12.2.0` publicado el 2026-10-13 (≥ 2 semanas); `dist/mermaid.min.js` (5,5 MB, IIFE que define
  `globalThis.mermaid`, con `initialize`, `run`, `suppressErrors`).

## AI output summary
- PLAN + AUDIT_PLAN: GO_CONDICIONAL (condiciones: E2E con `<svg>` en los dos informes; `/security-review` de
  `mermaid.ts` antes del merge).
- Backend: ajuste `mermaid_js` (`UBW_MERMAID_JS`); `compare_schemas(..., mermaid_js=)` → `mermaid_src`; el job
  avisa y genera sin Mermaid si el fichero falta. Tests: API (script incrustado, `</script>` escapado, sin
  `<script src=`) y unitario del fichero ausente.
- Frontend: dependencia `mermaid@12.2.0` (`--before=2026-10-16`); `renderMermaidBlocks` (nuevo `mermaid.ts`) en
  `MarkdownPreview`; tests con Mermaid simulado; `chunkSizeWarningLimit: 1600`.
- Docker: el runtime copia `node_modules/mermaid/dist/mermaid.min.js` a `/app/vendor/` y define `UBW_MERMAID_JS`.
- E2E de la comparación: `<svg>` en el informe (origen opaco, `no-mermaid` falso) y en la vista previa de
  `comparacion.md`.
- Docs: enmienda de ADR-007, guía de comparación, `architecture.md` (`UBW_MERMAID_JS`), GAPS G45 (abierto), CHANGELOG
  `[Unreleased]`.

## Evidencias
- Backend: ruff format/check, mypy; `pytest -m "not integration"` 702 passed / 2 skipped; `export_openapi.py --check`
  sin cambios. La suite completa dio 27 failed + 70 errors, todos en `tests/integration` (bench parado salvo
  PostgreSQL).
- Frontend: format, lint, typecheck, Vitest 134 tests, build sin avisos.
- Docs: `zensical build --strict`.
- `docker compose up -d --build`: `/app/vendor/mermaid.min.js` (5 494 801 bytes) en la imagen.
- E2E: `compare.spec.ts` passed; resto passed salvo `connections.spec.ts:79`, que pasó tras levantar
  `util_bbdd_bench_postgres` (estaba parado). Los fallos de login al repetir eran el rate limit de login.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| IMPLEMENT backend | `backend/app/core/config.py`, `backend/app/integrations/util_bbdd/compare.py`, `backend/app/jobs/operations/compare.py`, tests | completado |
| IMPLEMENT frontend | `frontend/src/features/runs/mermaid.ts` (nuevo), `ArtifactBrowser.tsx`, `mermaid.test.ts` (nuevo), `e2e/compare.spec.ts`, `vite.config.ts`, `package.json`, `package-lock.json` | completado |
| Imagen | `docker/Dockerfile` | completado |
| Docs | ADR-007, `docs/guides/comparacion.md`, `docs/architecture.md`, `docs/plan/UTIL_BBDD_GAPS.md` (G45), `CHANGELOG.md` | completado |

## Directrices para Futuras IAs
- **[comparación]**: el informe HTML lleva Mermaid incrustado (`mermaid_src=Path(UBW_MERMAID_JS)`); sin el ajuste o
  sin el fichero se genera con `mermaid_src=None` (texto). La imagen `backend-dev` (CI) no lo tiene: los tests del CI
  cubren el caso sin Mermaid y uno con un `mermaid.min.js` falso vía `monkeypatch.setenv` (el job es un subproceso
  *spawn* que relee el entorno).
- **[dependencias]**: la versión de Mermaid del informe HTML es la de `frontend/package-lock.json`; subirla allí
  cambia a la vez la vista previa del Markdown y la del informe. Comprobar que `dist/mermaid.min.js` siga existiendo
  y definiendo `globalThis.mermaid` (lo usa la plantilla de util_bbdd).
- **[frontend]**: `renderMermaidBlocks` solo importa `mermaid` si el HTML de `marked` tiene
  `pre > code.language-mermaid`; jsdom no puede dibujar, así que los tests simulan `mermaid` con `vi.mock`.
- **[E2E]**: `connections.spec.ts:79` necesita `util_bbdd_bench_postgres` (`postgres:17`, 127.0.0.1:55432) del
  `docker-compose.bench.yml` de util_bbdd, no otros PostgreSQL de la máquina; repetir specs con login en menos de un
  minuto choca con el rate limit de login.

## Veredicto final
Veredicto: GO (`/security-review` sin CRITICAL ni HIGH en el alcance; condición del AUDIT_PLAN cumplida)
Pendientes al cierre:
- LOW de la revisión de seguridad (`escape_mermaid_label` de util_bbdd no escapa saltos de línea): remediado en la
  web con `stripMermaidConfig` (directivas y frontmatter fuera antes de dibujar el Markdown) y pedido a util_bbdd
  como G46; el informe HTML sigue acotado por su sandbox hasta que util_bbdd lo resuelva.
- Fuera de alcance: `npm audit` avisa de `zod` 4.6.5 (GHSA-mrhx-c7xc-m3w5, high), dependencia previa.
- Release (1.8.0) cuando se pida; merge de `feat/mermaid12`.
- G45 en util_bbdd (subir `MERMAID_VERSION` a 12.x).
