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

## Documentación

La documentación vive en `docs/` y se lee igual en GitHub y como sitio [Zensical](https://zensical.org)
(`zensical.toml` en la raíz, dependencia del grupo `docs` de `backend/pyproject.toml`):

```bash
uv run --frozen --project backend --only-group docs zensical serve            # http://127.0.0.1:8000
uv run --frozen --project backend --only-group docs zensical build --strict   # lo que comprueba el CI
```

Python-Markdown es más estricto que GitHub: lo anidado en listas, a 4 espacios, y línea en blanco antes de
listas y tablas (reglas en `.github/instructions/docs.instructions.md`). El sitio se genera en `site/` (ignorado).

## Cambiar la API

1. Router y esquemas en `backend/app/api/v1/`.
2. `cd backend && uv run --frozen python scripts/export_openapi.py` (o con la imagen `backend-dev`); con `--check`
   solo comprueba que `openapi/openapi.json` está al día (lo hace el CI).
3. `cd frontend && npm run gen:api`.
4. Usa los tipos de `src/api/schema.d.ts` en un hook de TanStack Query.

El OpenAPI es la documentación de la API: `summary`, docstring y `responses` de cada endpoint y `Field(description=…)`
de los esquemas. En `development` se consulta en `/api/docs`.

## Validar antes de pedir revisión

Los comandos de [SHARED_INSTRUCTIONS.md § «Comandos de desarrollo»][comandos].

[comandos]: https://github.com/fmanza/util_bbdd_web/blob/develop/.github/SHARED_INSTRUCTIONS.md#comandos-de-desarrollo

## Dónde está cada cosa

- Plan: [ROADMAP](../plan/ROADMAP.md) · Decisiones: [adr/](../adr/) · Arquitectura:
  [architecture.md](../architecture.md)
- Problemas frecuentes: [troubleshooting.md](troubleshooting.md) · Despliegue: [deployment.md](deployment.md)

## E2E completa (Fase 10)

El CI la ejecuta en cada push, en cada PR y los lunes (job `e2e`), sin el bench de motores reales. En local, con la
imagen levantada, `scripts/e2e_prepare.sh` crea el admin E2E y copia a `/data/files` las BD SQLite de
`e2e/fixtures/` (se puede repetir):

```bash
export UBW_E2E_ADMIN_USER=e2e-admin UBW_E2E_ADMIN_PASSWORD="$(openssl rand -base64 24)" UBW_E2E_SQLITE=1
scripts/e2e_prepare.sh
cd frontend && npx playwright test --workers=2
```

Para no tocar los datos de tu instancia, levanta otra con sus propios volúmenes: `COMPOSE_PROJECT_NAME=ubw-e2e
UBW_PORT=8082` en el `docker compose up` y en el script, y `UBW_E2E_URL=http://127.0.0.1:8082` en Playwright.

- Credenciales en `UBW_E2E_ADMIN_USER`/`UBW_E2E_ADMIN_PASSWORD`; `UBW_E2E_SQLITE=1` para bulk, compare, documentación,
  dump, explorador y plantillas (BD en `/data/files`, ver la cabecera de cada spec); `UBW_E2E_MIGRATE=1` y el bench para
  la migración.
- Todos los specs importan `test` de `e2e/fixtures.ts`, que falla ante una violación de la CSP de la SPA.
- La suite hace muchos inicios de sesión desde la misma IP: arranca el compose con límites altos,
  `UBW_RATE_LIMIT_ANONYMOUS_PER_MINUTE=2000 UBW_RATE_LIMIT_LOGIN_PER_MINUTE=300 UBW_RATE_LIMIT_LOGIN_FAILURES=100
  docker compose up -d`, y ejecuta `npx playwright test --repeat-each=2 --workers=2`.
- La API sirve cookies `Secure` (`__Host-`): Chromium las acepta en `http://127.0.0.1`, httpx y PowerShell no
  (`scripts/load_test.py` las gestiona a mano).

## Auditoría de dependencias

El job `audit` del CI (en cada push, en cada PR y los lunes) ejecuta:

| Qué | Herramienta | Si encuentra algo |
|---|---|---|
| Python (`backend/uv.lock`) | `pip-audit` sobre `uv export` | Falla |
| npm de producción | `npm audit --omit=dev` | Falla |
| npm de desarrollo (eslint, Vitest, Playwright…) | `npm audit` | Solo avisa |

Si falla, actualiza el paquete respetando la regla de las dos semanas (`uv lock --upgrade-package <paquete>`;
`npm update <paquete> --before=<fecha>`). Si no hay versión corregida, añade una excepción con `--ignore-vuln <id>`
en `.github/workflows/ci.yml`, su motivo en los riesgos aceptados de
[ASVS_L2.md](../security/ASVS_L2.md#riesgos-aceptados) y una fecha de revisión en esta tabla:

| Excepción | Paquete | Motivo | Revisar |
|---|---|---|---|
| `PYSEC-2026-217` (CVE-2026-44172) | `mariadb` 1.1.14, vía util_bbdd | Sin versión corregida; afecta al escape manual con `big5`. util_bbdd no pasa `charset` al conector y la web usa parámetros enlazados | 2027-02-26 |

`pip-audit` no revisa util_bbdd (se instala por URL) ni los paquetes del sistema de la imagen (`libmariadb`…).
