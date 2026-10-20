# CONTEXT SNAPSHOT

## Contexto del repositorio revisado
- `.ai/product.md`, `.ai/architecture.md`, `.ai/sessions/2026-10-20-fase1/TRACEABILITY.md`
- `docs/plan/ROADMAP.md` (Fase 2), `docs/plan/UTIL_BBDD_GAPS.md`, `docs/adr/ADR-004`, `docs/adr/ADR-006`
- `.github/instructions/security.instructions.md` (secretos, conexiones salientes, ficheros)
- `backend/app/integrations/util_bbdd/__init__.py`, `scripts/generate_secrets.py`
- util_bbdd 4.0.0 **instalado** (`backend/.venv/.../util_bbdd`): `managers/sync_mgr.py`, `core/capabilities.py`,
  `connection/builder.py`, `connection/performance_advisor.py`, `connection/_advisory.py`, `migrate/planner.py`,
  `exceptions.py`, `_drivers/validator.py`
- `util_bbdd/docker-compose.bench.yml` (usuarios, BD y puertos de los bench; la contraseña no está en el repo)

## Estado actual observado
- Fase 1 cerrada (0.2.0, commit `b74eeb7`): 73 tests de backend y 19 de Vitest en verde.
- Bench en marcha: PostgreSQL 55432, MySQL 53306, MariaDB 53307, SQL Server **51833** (no el 51433 por defecto),
  Oracle 51521 y HSQLDB 59001.
- `UTIL_BBDD_BENCH_PASSWORD` definida como variable de usuario, pero no visible en el proceso de VS Code (sin
  reiniciar): se carga solo en el proceso de pytest/Playwright.

## Estado Git relevante
- Rama activa: develop
- Cambios locales pre-existentes: ninguno
- Último tag / versión publicada: 0.2.0 (sin tag)

## Clasificación metodológica
- Tipo principal: phase
- Estado real de alcance: acotado (Fase 2 del ROADMAP)
- Consecuencia: PLAN + AUDIT_PLAN y parada para aprobación

## Gate G0 · Context Ready
Veredicto: GO
Condiciones pendientes (si aplica):
- Ninguna (las de AUDIT_PLAN se resolvieron con el usuario)
