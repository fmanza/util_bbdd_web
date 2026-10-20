# REQUEST

## Session metadata
- id: 2026-10-20-fase1
- fecha: 2026-10-20
- rama: develop
- skill: phase
- fase solicitada: Fase 1 completa (PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION)

## Solicitud original saneada
`/phase` — Fase: 1. Alcance: completa. Mejoras opcionales: no. Restricciones: dependencias nuevas permitidas:
`pwdlib[argon2]`; sin servicios externos.

## Objetivo operativo de esta sesión
- Usuarios con roles `admin`/`user`, alta, desactivación y reactivación por un admin.
- Inicio y cierre de sesión con cookie de servidor + CSRF (ADR-003) y cambio de contraseña.
- Sesiones activas revocables y registro de auditoría consultable por el admin.
- CLI `create-admin`, frontend con login, guardas y administración; E2E de login.

## Restricciones explícitas
- Única dependencia nueva: `pwdlib[argon2]` (por eso los formularios no usan React Hook Form + Zod).
- Sin servicios externos; no adelantar historias de fases posteriores.
- Sin commits ni push salvo petición.

## Resultado esperado
- `util_bbdd_web` 0.2.0 con la DoD común y la de la Fase 1 cumplidas.
