# REQUEST

## Session metadata
- id: 2026-10-19-fase0
- fecha: 2026-10-19
- rama: develop
- skill: phase
- fase solicitada: Fase 0 completa (PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION)

## Solicitud original saneada
Aplicar las 4 correcciones del AUDIT_PLAN al prompt `util_bbdd/.github/prompts/web_project_bootstrap.prompt.md`
y lanzar la Fase 0 completa: crear `C:\Desarrollo\python\libs\util_bbdd_web` con estructura, configuración IA para
Copilot y Claude, plan por fases, Docker y esqueleto ejecutable.

## Objetivo operativo de esta sesión
- Proyecto creado con backend, frontend, Docker y CI ejecutables y validados.
- Configuración IA (Claude Code + Copilot) adaptada a una aplicación web.
- ROADMAP de 11 fases, `UTIL_BBDD_GAPS.md` y ADR-001…006.

## Restricciones explícitas
- No modificar util_bbdd (salvo el prompt de bootstrap, pedido explícitamente).
- No implementar funcionalidad de fases posteriores.
- Sin commits ni push.

## Resultado esperado
- `util_bbdd_web` 0.1.0 con `/api/health` 200 en `docker compose up` y suites en verde.
