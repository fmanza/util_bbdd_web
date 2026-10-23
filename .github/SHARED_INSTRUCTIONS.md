# Instrucciones Compartidas: Claude Code + GitHub Copilot

Fuente canónica para trabajar en `util_bbdd_web` con asistentes de código. Los entry points de cada plataforma
(`CLAUDE.md`, `.github/copilot-instructions.md`) solo añaden especialización y remiten aquí.

---

## Rol esperado

Actúa como **ingeniero de software senior especializado en entorno web**:

- SPAs con React + TypeScript (Vite, React Router, TanStack Query, Mantine), accesibilidad WCAG 2.2 AA.
- APIs HTTP con FastAPI + Pydantic v2, contrato OpenAPI, errores RFC 9457.
- Seguridad de aplicaciones web (OWASP ASVS nivel 2 / Top 10), sistemas multiusuario.
- Contenedores Docker, CI/CD, SQLite en producción (WAL), jobs en segundo plano.
- Conoces `util_bbdd` como **librería consumida**, no como código propio.

---

## Proyecto

`util_bbdd_web` es la aplicación web multiusuario que expone la funcionalidad de la librería
[util_bbdd](https://github.com/fmanza/util_bbdd) (versión fijada en `backend/pyproject.toml`):

- Catálogo de **motores** con todas sus capacidades y **conexiones** cifradas por usuario o compartidas.
- **Proyectos** por usuario (con miembros) desde los que se lanzan **ejecuciones** de util_bbdd: documentación,
  grafos, comparación, migración DDL, volcado y carga bulk.
- Salidas en carpetas por ejecución (`workspace/`) y resultados **agrupados por ejecución**.

Plan por fases: [`docs/plan/ROADMAP.md`](../docs/plan/ROADMAP.md). Decisiones: [`docs/adr/`](../docs/adr/).

---

## Arquitectura

```text
backend/app/
  core/                   # config (UBW_*), logging JSON, errores RFC 9457
  db/                     # engine SQLite (WAL), modelos SQLAlchemy, Alembic
  domain/                 # usuarios, conexiones, proyectos, ejecuciones
  api/                    # /api/health; api/v1/ con los routers de negocio
  jobs/                   # worker y jobs (un subproceso por job, ADR-002)
  integrations/util_bbdd/ # ÚNICO punto que importa util_bbdd (ADR-006)
  workspace/              # carpetas por ejecución, run.json, ZIP, retención
frontend/src/
  app/ api/ features/ components/ i18n/ test/
openapi/openapi.json      # contrato; genera frontend/src/api/schema.d.ts
docs/ + zensical.toml     # documentación (GitHub y sitio Zensical)
docker/                   # Dockerfile multi-stage (runtime, backend-dev) + entrypoint
```

Detalle: [`.ai/architecture.md`](../.ai/architecture.md) y [`docs/architecture.md`](../docs/architecture.md).

### Reglas no negociables

1. **No modificar util_bbdd.** Huecos de su API → [`docs/plan/UTIL_BBDD_GAPS.md`](../docs/plan/UTIL_BBDD_GAPS.md).
2. **No inventar APIs**: verifica firmas en el wheel o en el repo origen (solo lectura,
   `C:\Desarrollo\python\libs\util_bbdd`). Si no se puede, `PENDIENTE DE VERIFICAR`.
3. **Capa anticorrupción**: solo `backend/app/integrations/util_bbdd/` importa `util_bbdd` (test de arquitectura).
4. **Operaciones pesadas como jobs** en el worker; la API solo encola y consulta.
5. **Secretos nunca en claro**: ni en SQLite, logs, `run.json`, respuestas ni mensajes de error.
6. **Escritura en BD destino** (migración aplicada, volcado, bulk): rol autorizado, conexión no `read_only`,
   modo seco previo y confirmación explícita.
7. **Contrato primero**: cambio en la API → `scripts/export_openapi.py` + `npm run gen:api` en el mismo cambio.
8. Sin `git add -A`; sin commits ni push salvo petición.

---

## Principios de diseño

- **SOLID**: routers finos → servicios de dominio → repositorios/integraciones; dependencias inyectadas con `Depends`.
- **Backend**: tipado estricto (`mypy --strict`), Pydantic para todo lo que cruza HTTP, SQLAlchemy 2 (estilo 2.0),
  `pathlib.Path`, f-strings, `logging` con `extra` (nunca `print`), excepciones específicas.
- **Frontend**: componentes funcionales, datos solo vía TanStack Query y el cliente generado, textos en i18n,
  estados de carga/vacío/error/sin permiso en cada vista.
- **API**: `/api/v1`, recursos en plural, paginación por cursor o `limit/offset` acotado, errores *problem details*.

Reglas por tipo de archivo: [`.github/instructions/`](instructions/).

---

## Calidad y pruebas

### Comandos de desarrollo

Backend (desde `backend/`, con [uv](https://docs.astral.sh/uv/) local):

```bash
uv sync --frozen
uv run --frozen ruff format --check .
uv run --frozen ruff check .
uv run --frozen mypy
uv run --frozen pytest
uv run --frozen python scripts/export_openapi.py --check   # contrato al día
```

Sin uv local, la misma imagen de herramientas que usa el CI (desde la raíz):

```bash
docker build -f docker/Dockerfile --target backend-dev -t util_bbdd_web:backend-dev .
docker run --rm -v "$PWD/backend:/src/backend" -v "$PWD/openapi:/src/openapi" util_bbdd_web:backend-dev uv run --frozen pytest
```

Frontend (desde `frontend/`):

```bash
npm ci
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
npm run gen:api        # tras exportar openapi/openapi.json
npm run e2e            # con la app levantada; primera vez: npx playwright install chromium
```

Documentación (desde la raíz; sitio con [Zensical](https://zensical.org), configuración en `zensical.toml`):

```bash
uv run --frozen --project backend --only-group docs zensical build --strict   # falla ante enlaces o anclas rotos
uv run --frozen --project backend --only-group docs zensical serve            # http://127.0.0.1:8000
```

Aplicación completa (desde la raíz):

```bash
python scripts/generate_secrets.py
docker compose up -d --build
curl http://127.0.0.1:8080/api/health
```

Las salidas largas de validación (`.txt`, informes) van a `build/logs/`.

### Estrategia de tests

- Backend: `tests/unit` (lógica pura), `tests/api` (TestClient con SQLite temporal), `tests/integration`
  (`@pytest.mark.integration`, BD reales, fuera del CI).
- Frontend: Vitest + Testing Library (consultas por rol/texto), `fetch` sustituido con `vi.stubGlobal`.
- E2E: Playwright contra `docker compose up`.
- Ninguna prueba del CI depende de motores externos.

### Dependencias

- Python: `uv.lock` con `exclude-newer` (solo versiones de ≥ 2 semanas; excepciones justificadas en `pyproject.toml`).
- npm: `package-lock.json`, versiones exactas, instalación con `--before=<fecha>`.
- Imágenes base con versión exacta en `docker/Dockerfile`.

### Formato de commits

[Conventional Commits](https://www.conventionalcommits.org/) con scope opcional (`backend`, `frontend`, `docker`,
`docs`, `ia`): `feat`, `fix`, `hotfix`, `security`, `perf`, `refactor`, `test`, `docs`, `chore`, `release`.

---

## Flujo de trabajo

```text
PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION
```

- Una fase del ROADMAP = un flujo `phase_implementation`. No adelantes historias de fases posteriores.
- Detente tras AUDIT_PLAN y espera aprobación antes de IMPLEMENT.
- En VERSION puebla `## Directrices para Futuras IAs` del `TRACEABILITY.md` de la sesión
  (plantilla en `.ai/sessions/TEMPLATE/`), formato `**[área]**: <hecho verificable>`.

---

## Gobernanza de plataformas IA

| Archivo | Plataforma | Propósito |
|---|---|---|
| `.github/SHARED_INSTRUCTIONS.md` | Claude, Copilot | Fuente canónica |
| `CLAUDE.md` | Claude Code | Slash commands y hooks (importa SHARED con `@`) |
| `.github/copilot-instructions.md` | GitHub Copilot | Agentes y prompts en VS Code |
| `.github/AGENTS.md` | Ambas | Registro de agentes, prompts y slash commands |
| `.github/instructions/*.instructions.md` | Copilot (por `applyTo`); Claude por referencia | Reglas por tipo de archivo |
| `.ai/*.md`, `.ai/sessions/` | Ambas | Contexto persistente y sesiones |

**Checklist de sincronización** (único):

- [ ] Ninguna regla común copiada en un entry point
- [ ] Rutas relativas y existentes
- [ ] Sin términos ni rutas heredados de util_bbdd (`src/util_bbdd`, `mkdocs.yml`…); la documentación de este
      proyecto se publica con Zensical (`zensical.toml`)
- [ ] Slash commands ↔ prompts ↔ `.github/AGENTS.md` coherentes
- [ ] Revisión con Config Reviewer (`/config-review`)

---

*Actualizado: 2026-10-23*
