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
