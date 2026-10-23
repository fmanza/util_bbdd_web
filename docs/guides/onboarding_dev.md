# Guía de incorporación para desarrolladores

## Requisitos

| Herramienta | Versión | Para qué |
|---|---|---|
| Docker Desktop / Engine | 29+ con Compose v2 | Imagen y arranque completo |
| Node.js | 24 LTS | Frontend |
| uv | 0.12.x (opcional) | Backend en local; sin uv se usa la imagen `backend-dev` |
| Git | — | — |

## Primer arranque

Sigue [Puesta en marcha › En local](puesta_en_marcha.md#3-en-local). Tienes tres formas:

- **Probar la imagen**: `docker compose up -d --build`, en <http://127.0.0.1:8080>.
- **Desarrollar sin Docker**: API con uv y `--reload` en el puerto 8000, worker y Vite en <http://localhost:5173>.
  Los tres procesos necesitan los mismos `UBW_FERNET_KEYS`/`UBW_APP_SECRET_KEY`.
- **Desarrollar con la API en Docker**: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
  web worker` y Vite en el equipo.

En `development` las cookies no llevan `Secure` ni el prefijo `__Host-`, y `/api/docs` está disponible. En `test` y
`production` sí lo llevan; los tests usan `https://testserver`.

## Desarrollo diario

Sin worker, las ejecuciones se quedan en cola (`/api/health` → `"worker": "absent"`).

**Pruebas de integración** contra los contenedores bench de util_bbdd (`docker-compose.bench.yml`, fuera del CI):
con `UTIL_BBDD_BENCH_PASSWORD` definida, `cd backend && uv run pytest -m integration tests/integration`. Los puertos
se cambian con `UTIL_BBDD_BENCH_<MOTOR>_PORT`, igual que en el compose. Si un contenedor publica otro puerto, el
real se consulta con `docker port <contenedor>` (p. ej. SQL Server: `UTIL_BBDD_BENCH_MSSQL_PORT`).

**Frontend** (proxy de `/api` a `127.0.0.1:8000`):

```bash
cd frontend
npm ci
npm run dev        # http://localhost:5173 (en Windows, 127.0.0.1 puede no responder)
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
