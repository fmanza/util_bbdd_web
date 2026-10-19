# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versiones según
[SemVer](https://semver.org/lang/es/). Hasta 1.0, una MINOR por fase del ROADMAP.

## [0.1.0] - 2026-10-19

Fase 0 — Fundaciones.

### Added

- **Backend**: FastAPI con fábrica `create_app`, `/api/health` (estado de `config.db` y versiones), errores
  `application/problem+json` (RFC 9457), logging JSON, ajustes `UBW_*` y Docker secrets, SQLite con WAL y
  `foreign_keys`, Alembic (revisión vacía `0001`), capa anticorrupción `integrations/util_bbdd` con test de
  arquitectura, worker esqueleto, export de OpenAPI con `--check`.
- **Frontend**: Vite + React + TypeScript estricto, Mantine, TanStack Query, React Router, i18n en español,
  cliente tipado generado desde OpenAPI, layout con navegación por fases, página de inicio con el estado del
  servicio, 404 de la SPA, tests con Vitest y E2E de humo con Playwright.
- **Docker**: imagen multi-stage (`runtime`, `backend-dev`), variantes `WITH_HSQLDB` / `WITH_ODBC`, compose con
  `web` y `worker` (perfil), volúmenes `data` y `workspace`, secretos, usuario no root, `read_only`, `cap_drop`.
- **CI**: backend (ruff, mypy, pytest, contrato OpenAPI), frontend (prettier, eslint, tsc, vitest, cliente al día,
  build) e imagen con arranque y `/api/health`; Dependabot con *cooldown* de 14 días.
- **Documentación**: ROADMAP de 11 fases, `UTIL_BBDD_GAPS.md` (G1–G9), ADR-001…006, arquitectura, guías de
  incorporación, despliegue y solución de problemas.
- **Configuración IA**: `SHARED_INSTRUCTIONS.md`, `CLAUDE.md`, `copilot-instructions.md`, 8 instrucciones por ruta,
  11 agentes (nuevo: Frontend Reviewer), 9 prompts (nuevo: `phase_implementation`), 9 slash commands (nuevo:
  `/phase`), hooks de Claude Code.

### Dependencias

- util_bbdd 4.0.0 vendorizado; Python resuelto con `exclude-newer = 2026-10-05` (excepción: asyncpg);
  npm instalado con `--before=2026-10-05`.
