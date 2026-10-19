# TRACEABILITY

## Session metadata
- id: 2026-10-19-fase0
- fecha: 2026-10-19
- rama: develop
- skill: phase
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION (Fase 0 del ROADMAP)

## Prompt issued
«las 4 correcciones al prompt y lanza la Fase 0 completa»

## Context supplied
- PLAN y AUDIT_PLAN emitidos en la sesión anterior (veredicto GO_CONDICIONAL con 4 correcciones y G1–G8)
- `util_bbdd/.github/prompts/web_project_bootstrap.prompt.md`

## AI output summary
- Prompt de util_bbdd corregido: firma de `SchemaComparator` (Inspector), motores de migración, `pymssql` sin ODBC,
  subproceso por job en ADR-002, `fichero_salida` + `batch_window_seconds=0` en documentación.
- `git init` (main → develop) en `util_bbdd_web`; wheel util_bbdd 4.0.0 copiado a `vendor/wheels/`.
- Backend FastAPI (core, db, api, integrations, jobs/worker), Alembic `0001`, script de OpenAPI, 12 tests.
- `uv.lock` generado con uv 0.12.22 en contenedor; `exclude-newer` 2026-10-05 + excepción asyncpg.
- Frontend con npm `--before=2026-10-05`; TypeScript fijado a 5.9 por incompatibilidades (ver Directrices).
- Docker: `runtime`, `backend-dev`, variantes HSQLDB/ODBC; compose con `web` y `worker` (perfil) y secretos.
- Configuración IA: SHARED, CLAUDE.md, copilot-instructions, AGENTS.md, 8 instructions, 11 agentes, 9 prompts,
  9 commands, hooks; plantilla de sesión adaptada.
- Docs: ROADMAP, UTIL_BBDD_GAPS (G1–G9), ADR-001…006, arquitectura y 3 guías.
- AUDIT_CODE: backend ruff/format/mypy/pytest (12 passed)/OpenAPI `--check` OK; frontend prettier/eslint/tsc/
  vitest (3 passed)/gen:api/build OK; `docker compose build` + `up`: web *healthy*, `/api/health` → `ok`, SPA
  servida, worker arranca y para con SIGTERM, usuario uid 10001, FS de solo lectura; enlaces Markdown OK; sin
  referencias heredadas de util_bbdd. Salidas en `build/logs/fase0_*.txt`.
- No ejecutado: E2E de Playwright (requiere descargar Chromium) y el workflow de CI en GitHub.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Prompt corregido | `util_bbdd/.github/prompts/web_project_bootstrap.prompt.md` | completado |
| Backend | `backend/` | completado |
| Frontend | `frontend/` | completado |
| Docker | `docker/`, `docker-compose*.yml` | completado |
| CI | `.github/workflows/ci.yml`, `.github/dependabot.yml` | creado, no ejecutado |
| Configuración IA | `.github/`, `.claude/`, `CLAUDE.md`, `.ai/` | completado |
| Plan y ADRs | `docs/plan/`, `docs/adr/` | completado |

## Directrices para Futuras IAs
- **[dependencias-ts]**: TypeScript debe quedarse en 5.9: `openapi-typescript` 7.13 exige `^5` y `typescript-eslint` 8.71 `<6.1`; TS 7 rompe ambos (verificado 2026-10-19).
- **[dependencias-py]**: `uv lock` usa `exclude-newer = 2026-10-05`; util_bbdd 4.0.0 exige `asyncpg>=0.32` (posterior) y por eso hay `exclude-newer-package` para asyncpg.
- **[herramientas]**: el equipo no tiene `uv` local: `uv lock` se ejecuta con `docker run python:3.12.14-slim-bookworm` + `pip install uv==0.12.22`, y la validación con la imagen `--target backend-dev` montando `backend/` y `openapi/`. Las imágenes `ghcr.io/astral-sh/uv:<ver>-python3.12-bookworm-slim` no existen para 0.12.22; solo `ghcr.io/astral-sh/uv:0.12.22` (binario).
- **[frontend-build]**: los tsconfig necesitan `"noEmit": true`; sin él, `tsc -b` emite `.js` junto a los `.tsx` y Vite resuelve `.js` antes que `.tsx`.
- **[frontend-tests]**: `openapi-fetch` captura `fetch` al crear el cliente; `src/api/client.ts` pasa `fetch: (r) => globalThis.fetch(r)` para que `vi.stubGlobal('fetch', …)` funcione. `baseUrl` es `location.origin` porque el `Request` de Node no acepta URLs relativas.
- **[backend-config]**: pydantic-settings aplica el prefijo `UBW_` también a los Docker secrets: los ficheros se llaman `ubw_app_secret_key` y `ubw_fernet_keys`.
- **[ruff]**: la carpeta `backend/alembic/` hace que ruff tome `alembic` por first-party; está en `known-third-party`.
- **[util_bbdd]**: el wheel 4.0.0 vendorizado tiene SHA-256 `a9a71aec…29f60`; el repo de GitHub respondía 404 sin credenciales (ADR-006).
- **[imagen]**: la imagen runtime mide 766 MB sin comprimir (pandas, Graphviz, drivers); medir de nuevo al añadir dependencias.
- **[starlette]**: Starlette 1.x avisa `StarletteDeprecationWarning` por usar `httpx` en `TestClient` (recomienda `httpx2`); pendiente de decidir.

## Veredicto final
Veredicto: CLOSED (Fase 0 cumplida; DoD salvo E2E y CI remoto, no ejecutados)
Pendientes al cierre:
- Ejecutar E2E (`npx playwright install chromium` + `npm run e2e` con la app levantada).
- Primer push y ejecución del CI en GitHub (el usuario hace el push).
- Bundle del frontend > 500 kB: carga diferida de rutas a partir de la Fase 2.
- Aviso `httpx2` de Starlette.
- Siguiente paso: `/phase 1` desde `util_bbdd_web`.
