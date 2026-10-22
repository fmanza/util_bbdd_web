# CONTEXT SNAPSHOT

## Contexto del repositorio revisado
- `docs/plan/ROADMAP.md` (Fase 3), `docs/adr/ADR-002-ejecucion-de-jobs.md`, `docs/adr/ADR-005-workspace-y-ejecuciones.md`
- `backend/app/jobs/worker.py` (esqueleto de la Fase 0), `docker-compose.yml` (worker en perfil), `.github/workflows/ci.yml`
- util_bbdd 4.0.0 instalado: `audit/contracts.py` (`AuditSink`, `@runtime_checkable`), `audit/events.py`
  (`AuditEvent`, `as_dict()`, `message` puede llevar valores de clave)
- FastAPI 0.142: `fastapi.sse` (`EventSourceResponse`, `ServerSentEvent`, *keepalive* integrado)
- SQLite de la imagen: 3.40.1 (admite `UPDATE … RETURNING`)

## Estado actual observado
- Fase 2 cerrada (0.3.0, commit `066b0b9`): 151 tests de backend, 39 de Vitest, 9 E2E.
- `mypy` en Windows fallaba en `worker.py` por `signal.sigwait` (solo Linux).

## Estado Git relevante
- Rama activa: develop
- Cambios locales pre-existentes: ninguno
- Último tag / versión publicada: 0.3.0 (sin tag)

## Clasificación metodológica
- Tipo principal: phase
- Estado real de alcance: acotado (Fase 3 del ROADMAP)
- Consecuencia: PLAN + AUDIT_PLAN y parada para aprobación

## Gate G0 · Context Ready
Veredicto: GO
Condiciones pendientes (si aplica):
- Ninguna
