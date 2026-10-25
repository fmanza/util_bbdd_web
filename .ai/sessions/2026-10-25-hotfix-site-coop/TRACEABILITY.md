# TRACEABILITY

## Session metadata
- id: 2026-10-25-hotfix-site-coop
- fecha: 2026-10-25
- rama: develop
- skill: hotfix
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION + despliegue local

## Prompt issued
`/hotfix`: en el sitio HTML de la documentación, los enlaces que agrupan la numeración de los elementos y los enlaces
de los contenidos muestran «127.0.0.1 está bloqueado — 127.0.0.1 rechazó la conexión — ERR_BLOCKED_BY_RESPONSE».
Tras AUDIT_PLAN: «IMPLEMENT, con commit, despliegue y prueba».

## Context supplied
- Despliegue local (`C:\Desarrollo\Proyectos\web_bbdd\util_bbdd_web`) y la ejecución `01M5SKMTVDHFMM7P8K3AZNH4QJ`
  (SocyalPRO, 629 tablas).
- `HttpMiddleware._decorate` (`core/middleware.py`) y `_SITE_HEADERS` (`api/v1/runs.py`).

## AI output summary
- RCA:
  - los enlaces `target="_blank"` del sitio (tarjetas `collections/*_all.html` del índice y `detail-link` de las
    colecciones) abren ventanas que heredan el `sandbox` de la CSP;
  - el middleware ponía `Cross-Origin-Opener-Policy: same-origin` en todas las respuestas;
  - Chromium bloquea una ventana con `sandbox` cuya respuesta trae un COOP distinto de `unsafe-none`.
- Reproducción:
  - en el despliegue (URL firmada, Playwright): la tarjeta «Tablas» acaba en `chrome-error://` con respuesta 200 y
    `cross-origin-opener-policy: same-origin`;
  - en el servidor de pruebas del scratchpad, con las mismas CSP: `same-origin` se bloquea y `unsafe-none` abre la
    colección y el detalle desde ella.
- IMPLEMENT:
  - `_SITE_HEADERS` con `Cross-Origin-Opener-Policy: unsafe-none`;
  - test de API: índice, detalle y colección con `unsafe-none`; la API sigue con `same-origin` (fallaba antes);
  - E2E: tarjeta «Tablas» → pestaña con la colección → detalle de `pedidos` en otra pestaña;
  - ADR-007 (enmienda 2026-10-25) y CHANGELOG.
- Validación: ruff, mypy, `export_openapi.py --check`, pytest 565 passed (87 skipped), format:check, lint,
  typecheck, build, Vitest 105, `zensical build --strict` y E2E en un stack aislado temporal (19 passed, 2 skipped;
  eliminado al terminar).

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Fix | `backend/app/api/v1/runs.py` | completado |
| Tests | `backend/tests/api/test_documentation.py`, `frontend/e2e/documentation.spec.ts` | en verde |
| Docs | `docs/adr/ADR-007-sitio-html-aislado.md`, `CHANGELOG.md` | completado |
| Logs | `build/logs/hotfix-coop-*.txt` | generados |

## Directrices para Futuras IAs
- **[sitio-html]**: el sitio responde con `Cross-Origin-Opener-Policy: unsafe-none`; con `same-origin`, las pestañas
  `target="_blank"` que abre (heredan el `sandbox`) dan `ERR_BLOCKED_BY_RESPONSE`.
- **[sitio-html]**: nunca `allow-popups-to-escape-sandbox`: las pestañas tendrían el origen real (cookie y API).
- **[e2e]**: probar el sitio exige navegar al `detailFrame` y abrir pestañas desde el índice y desde una colección.

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Ninguno del hotfix; despliegue y prueba en el entorno local al cerrar la sesión.
