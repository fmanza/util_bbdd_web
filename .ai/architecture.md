# Arquitectura (contexto para IAs)

Fuente detallada: `docs/architecture.md` y `docs/adr/`. Resumen operativo:

## Niveles y dependencias permitidas

| Nivel | Paquete | Puede importar |
|---|---|---|
| 1 | `backend/app/core` | stdlib, pydantic-settings, Starlette/FastAPI (errores, middleware), prometheus-client |
| 1 | `backend/app/db` | core, SQLAlchemy |
| 2 | `backend/app/integrations/util_bbdd` | core, **util_bbdd** (único) |
| 2 | `backend/app/workspace` | core |
| 3 | `backend/app/domain` | core, db, integrations, workspace (sin FastAPI) |
| 4 | `backend/app/jobs` | core, db, domain, integrations, workspace |
| 4 | `backend/app/api` | core, db, domain (y `integrations` solo para lecturas triviales como la versión) |
| 5 | `backend/app/main.py` | api, core |

## Patrones con nombre

- **Capa anticorrupción (ACL)**: `integrations/util_bbdd` traduce objetos de util_bbdd a tipos propios.
- **Contrato primero**: OpenAPI exportado → cliente TypeScript generado.
- **Job en subproceso**: el worker lanza un proceso hijo por ejecución (cancelable, aislado).
- **Run manifest**: `run.json` en la carpeta de cada ejecución + filas en `runs`/`artifacts`.

## Flujo de una ejecución (Fase 3)

`POST /api/v1/projects/{id}/runs` (202) → fila `runs(queued)` → el worker la reclama (`UPDATE … RETURNING`) →
subproceso *spawn* con solo el `run_id` → operación (`app/jobs/operations`) → `workspace/.../outputs`, `run.json`,
`logs/run.log` → `finalize_run` registra `artifacts` → `runs(succeeded|failed|cancelled)` → SSE
(`/runs/{id}/events`) al navegador. Cancelar = `cancel_requested` → el worker termina el subproceso.
