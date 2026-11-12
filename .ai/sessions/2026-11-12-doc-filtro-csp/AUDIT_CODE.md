# AUDIT_CODE — 2026-11-12-doc-filtro-csp

Commits: `52b0380`, `a90a73c`, `8440a91`.

## Verificación

| Comprobación | Resultado |
|---|---|
| Backend `pytest -m "not integration"` (sin URLs del banco) | 801 passed, 2 skipped |
| `ruff format --check`, `ruff check`, `mypy` | limpios |
| `export_openapi.py --check` | al día |
| Frontend `format:check`, `lint`, `typecheck`, `npm test`, `build` | limpios; 203 tests |
| `zensical build --strict` | sin avisos |
| Chromium (Playwright) con `BRIDGE_SCRIPT` y `SPA_CSP` reales | enlace → `postMessage` al padre; ancla dentro; consola sin errores de CSP |
| E2E con la aplicación levantada | no ejecutado |

## Revisión de seguridad

- `SPA_CSP` añade solo `'sha256-…'` del puente: sin `'unsafe-inline'` ni `'unsafe-eval'`. El script autorizado solo
  escucha clics y envía `{type, href}` al origen de la SPA, que valida `event.source`, el formato y la longitud.
- El ancla y el origen van como atributos del `<body>` escapados (`&`, `"`, `<`, `>`); el contenido de la página pasa
  por DOMPurify y no puede ejecutar otro script.
- Los patrones del filtro se validan en el backend (una línea, ≤ 100 patrones de ≤ 128 caracteres) y util_bbdd los
  vuelve a validar; no llegan a SQL (se comparan en Python con `fnmatch`).
- El log de la documentación registra cuántas tablas tiene la frontera, no sus nombres.

Veredicto: **APROBADO**.
