# TRACEABILITY

## Session metadata
- id: 2026-11-12-doc-filtro-csp
- fecha: 2026-11-12
- rama: develop
- skill: new_feature + hotfix + version_closure (sesión hermana en util_bbdd: `2026-11-12-doc-filtro-relaciones`)
- fase: PLAN + AUDIT_PLAN (en util_bbdd) + IMPLEMENT (W1–W7) + AUDIT_CODE + VERSION → 1.15.0

## Prompt issued
Comentarios sobre la documentación: ficha Markdown y HTML más ancha, enlaces del Markdown que no funcionan,
instrucciones para ver la exportación Markdown, «pido un nivel de profundidad y salen 2», excluir tablas por patrón
con ayuda y alternativas de ayuda interactiva. Después «IMPLEMENT» y «Hazlo todo» (con la release de util_bbdd 5.5.0
publicada con `gh`, autorizado expresamente).

## Context supplied
- Código de la web 1.14.0; util_bbdd 5.5.0 (filtro, «Referenciada por», README, «Niveles por sentido»).

## AI output summary
- `52b0380` chore(backend): util_bbdd 5.5.0 (hash del lock = `.sha256` de la release; uv 0.12.22).
- `a90a73c` fix: **enlaces del visor Markdown**. Causa: el `srcdoc` hereda `SPA_CSP` (`script-src 'self'`) y bloqueaba
  el puente con nonce, reproducido en Chromium (Playwright). Puente constante autorizado por su `sha256` en las dos
  CSP; `test_spa_csp_allows_the_markdown_bridge_by_its_hash` vigila que coincidan; ADR-007 enmendado. Además, W1:
  documentación a todo el ancho y alto.
- `8440a91` feat: filtro de tablas (W5) con «Probar patrones» y ayuda (W6), README en la tarjeta Markdown (W3),
  descripciones de los niveles (W4), guía y G52–G54.
- AUDIT_CODE: [AUDIT_CODE.md](AUDIT_CODE.md) (APROBADO).

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| util_bbdd 5.5.0 | `52b0380` | completado |
| Enlaces + ancho | `a90a73c` | completado |
| Filtro, ayuda, README, niveles | `8440a91` | completado |
| AUDIT_CODE | [AUDIT_CODE.md](AUDIT_CODE.md) | APROBADO |
| Release | `release: v1.15.0` + tag local | pendiente de push y despliegue |

## Directrices para Futuras IAs
- **[frontend/visor Markdown]**: un `iframe srcdoc` hereda la CSP de la SPA aunque esté en `sandbox`. Cualquier script
  del `srcdoc` debe estar autorizado también por `SPA_CSP`. Si cambias `BRIDGE_SCRIPT` (`markdownFrame.ts`), recalcula
  `BRIDGE_SHA256` y `MARKDOWN_BRIDGE_SHA256` (`backend/app/core/middleware.py`); los tests de los dos lados fallan si no
  coinciden.
- **[frontend/tests]**: jsdom no aplica CSP: un fallo de CSP solo se ve en un navegador real con la cabecera del
  backend (Playwright con un servidor que la envíe; `vite dev` no la envía).
- **[frontend/filtro]**: `tablePatterns.ts` replica `fnmatch.fnmatchcase` de util_bbdd; `tablePatterns.cases.json`
  son 260 casos generados con Python. Si util_bbdd cambia la semántica de `TableFilter`, regenera los casos.
- **[backend]**: el frontend no tiene `@types/node`: en sus tests, Web Crypto (`crypto.subtle`), no `node:crypto`.

## Veredicto final
Veredicto: CLOSED (1.15.0)
Pendientes al cierre:
- Push de `develop`, CI en verde, ff de `main`, tag `v1.15.0` y despliegue (usuario, `publicar_version.md` §6–8).
- E2E con la aplicación levantada (`npm run e2e`): no ejecutado en esta sesión.
