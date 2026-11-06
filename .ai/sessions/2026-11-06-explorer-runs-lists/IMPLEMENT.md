# IMPLEMENT — Explorador, eliminación de ejecuciones y listas

Lanzado el 2026-11-07 («Hazlo», tras PLAN y AUDIT_PLAN aprobados con D1-D8). D6 enmendada: la ola 11 salió antes
como 1.13.0 y esta sesión es la **1.14.0**.

| Commit | Bloque | Contenido |
|---|---|---|
| `026d8c8` | A | Explorador a toda altura: árbol y ficha con el alto de la ventana en escritorio; cada pestaña en un `ScrollArea` de alto completo (vertical y horizontal) con `stickyHeader`; móvil con ficha de `70dvh`; «Copiar DDL» (D5). Causa del fallo: `ScrollArea` con solo `mah` no se desplaza |
| `ad95fd9` | — | Test intermitente de `auth.test.tsx` (esperas de 5 s, test de 15 s) |
| `f35ee3b` | B | `domain/runs/admin.py`, `api/v1/admin_runs.py`: lista de todos los proyectos (solo metadatos), borrado de una (409 activa o volcado pendiente) y por proyecto (`confirm` = nombre exacto en el servidor; omite activas y volcados pendientes); carpetas después del commit; auditoría `run.delete` y `project.runs_delete`; `relaunched_from_exists` (D7). `DataTable` común y `domain/sorting.py` |
| `f3409e6` | C | `sort`/`order` (lista blanca) en 8 endpoints, `q` en sesiones y auditoría, `LIKE` escapado; todas las listas de recursos con `DataTable` (servidor o cliente), 25 por página |
| `a8d94f6` | A | Alto medido cuando el contenedor ya existe (ref de callback): la vista medía 197 px de más (Chromium) |
| `bd549b6` | — | Guías, ROADMAP y CHANGELOG |

Ajustes respecto del PLAN: orden de ejecuciones sin `duration` (T6: expresión dependiente del motor); los selectores
de conexión piden 200 (no 25); `rowHeader` y `caption` en `DataTable` para conservar la semántica de las tablas.

## Validación

| Comando | Resultado |
|---|---|
| Backend `ruff format --check`, `ruff check`, `mypy` (127 ficheros), `export_openapi.py --check` | OK |
| `pytest -m "not integration"` | 793 passed, 2 skipped |
| Frontend `format:check`, `lint`, `typecheck`, `build` | OK |
| `npm test` | 198 passed |
| `zensical build --strict` | OK |
| Chromium (instancia local desechable, 1440×900 y 390×844) | Ver AUDIT_CODE |
