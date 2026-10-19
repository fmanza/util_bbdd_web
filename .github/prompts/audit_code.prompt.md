# Prompt: audit_code (aplicación web)

Auditoría técnica con veredicto final. Modo lectura: no edita código. Agente: Code Auditor (y Frontend Reviewer si
el alcance incluye `frontend/`).

## Inputs requeridos
- **Archivos a revisar**: rutas o globs (p. ej. `backend/app/api/v1/`, `frontend/src/features/connections/`)
- **Contexto**: qué cambió o por qué se audita
- **Foco**: bugs, seguridad, tipado, accesibilidad, tests o todo

Si no se especifican archivos, detente.

## Devuelve en este orden

### PLAN
- alcance y archivos analizados

### AUDIT_PLAN
- riesgos funcionales, técnicos y de seguridad

### AUDIT_CODE
- bugs potenciales (`archivo:línea`) y edge cases
- contrato HTTP: OpenAPI exportado = código; cliente regenerado; errores RFC 9457
- autorización por recurso (IDOR), secretos, path traversal
- concurrencia (SQLite, jobs) y manejo de recursos
- tipado (`Any`, `any`), accesibilidad, rendimiento
- tests faltantes o insuficientes
- **Veredicto:** `APROBADO | APROBADO CON CONDICIONES | RECHAZADO`

### VERSION
- commit message si hay cambios derivados (`fix:` o `refactor:`) y pruebas sugeridas

## Reglas
- Evidencias por archivo y línea; diferencia hallazgos confirmados de hipótesis.
