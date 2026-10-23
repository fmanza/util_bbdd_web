# Guía de incorporación para desarrolladores

## Requisitos

| Herramienta | Versión | Para qué |
|---|---|---|
| Docker Desktop / Engine | 29+ con Compose v2 | Imagen y arranque completo |
| Node.js | 24 LTS | Frontend |
| uv | 0.12.x (opcional) | Backend en local; sin uv se usa la imagen `backend-dev` |
| Git | — | — |

## Primer arranque

```bash
git clone <repo> util_bbdd_web && cd util_bbdd_web
python scripts/generate_secrets.py          # secrets/*.txt (git-ignored)
docker compose up -d --build
# http://127.0.0.1:8080
```

## Desarrollo diario

**Backend** con recarga en caliente (en Docker, puerto 8000):

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build web
```

o en local con uv: `cd backend && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:create_app --factory --reload --port 8000`.

Crea un administrador para entrar (no hay credenciales por defecto):

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec web python -m app.cli create-admin --username admin
# o en local: cd backend && uv run python -m app.cli create-admin --username admin
```

En `development` las cookies no llevan `Secure` (HTTP local); en `test` y `production` sí.

**Worker** en local (otra terminal): `cd backend && uv run python -m app.jobs.worker`. Sin worker, las ejecuciones
se quedan en cola (`/api/health` → `"worker": "absent"`).

**Pruebas de integración** contra los contenedores bench de util_bbdd (`docker-compose.bench.yml`, fuera del CI):
con `UTIL_BBDD_BENCH_PASSWORD` definida, `cd backend && uv run pytest -m integration tests/integration`. Los puertos
se cambian con `UTIL_BBDD_BENCH_<MOTOR>_PORT`, igual que en el compose.

**Frontend** (proxy de `/api` a `127.0.0.1:8000`):

```bash
cd frontend
npm ci
npm run dev        # http://127.0.0.1:5173
```

## Cambiar la API

1. Router y esquemas en `backend/app/api/v1/`.
2. `cd backend && uv run python scripts/export_openapi.py` (o con la imagen `backend-dev`).
3. `cd frontend && npm run gen:api`.
4. Usa los tipos de `src/api/schema.d.ts` en un hook de TanStack Query.

## Validar antes de pedir revisión

Los comandos de [SHARED_INSTRUCTIONS.md § «Comandos de desarrollo»](../../.github/SHARED_INSTRUCTIONS.md#comandos-de-desarrollo).

## Dónde está cada cosa

- Plan: [ROADMAP](../plan/ROADMAP.md) · Decisiones: [adr/](../adr/) · Arquitectura: [architecture.md](../architecture.md)
- Problemas frecuentes: [troubleshooting.md](troubleshooting.md) · Despliegue: [deployment.md](deployment.md)

## E2E completa (Fase 10)

Con la imagen levantada (`docker compose up -d --build`) y el admin E2E creado:

- Credenciales en `UBW_E2E_ADMIN_USER`/`UBW_E2E_ADMIN_PASSWORD`; `UBW_E2E_SQLITE=1` para dump, bulk, compare y
  documentación (BD en `/data/files`, ver la cabecera de cada spec); `UBW_E2E_MIGRATE=1` y el bench para la migración.
- Todos los specs importan `test` de `e2e/fixtures.ts`, que falla ante una violación de la CSP de la SPA.
- La suite hace muchos inicios de sesión desde la misma IP: arranca el compose con límites altos,
  `UBW_RATE_LIMIT_ANONYMOUS_PER_MINUTE=2000 UBW_RATE_LIMIT_LOGIN_PER_MINUTE=300 UBW_RATE_LIMIT_LOGIN_FAILURES=100
  docker compose up -d`, y ejecuta `npx playwright test --repeat-each=2 --workers=2`.
- La API sirve cookies `Secure` (`__Host-`): Chromium las acepta en `http://127.0.0.1`, httpx y PowerShell no
  (`scripts/load_test.py` las gestiona a mano).
