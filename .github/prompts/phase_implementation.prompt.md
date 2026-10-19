# Prompt: phase_implementation — Implementar una fase del ROADMAP

Implementa **una** fase de `docs/plan/ROADMAP.md` completa, con su Definición de Hecho (DoD).
Agentes: Plan Architect (PLAN + AUDIT_PLAN) → Feature Implementer (IMPLEMENT) → Code Auditor + Frontend Reviewer
(+ Security Reviewer si la fase toca autenticación, secretos o escritura en BD) (AUDIT_CODE) → Version Closer (VERSION).

## Inputs requeridos
- **Fase**: número (p. ej. `2`)
- **Alcance**: `completa` o lista de historias de la fase
- **Mejoras opcionales** de la fase a incluir: sí/no y cuáles
- **Restricciones**: dependencias nuevas permitidas, motores disponibles para probar, plazos

Si falta alguno o la fase anterior no está cerrada en el ROADMAP, detente y aclara.

## Devuelve en este orden

### PLAN
- historias de usuario de la fase y DoD
- contrato HTTP: endpoints, esquemas, códigos de error
- modelo de datos y migración Alembic
- uso de util_bbdd con **firmas verificadas** (o `PENDIENTE DE VERIFICAR`)
- pantallas y componentes del frontend
- riesgos (seguridad, concurrencia de SQLite, operaciones destructivas, tamaño de imagen)
- estrategia de pruebas

### AUDIT_PLAN
- contraste con `.ai/architecture.md`, reglas no negociables de SHARED y ADRs
- huecos de util_bbdd nuevos (para `UTIL_BBDD_GAPS.md`)
- **Veredicto:** `GO | GO_CONDICIONAL | NO_GO`. Detente y espera aprobación.

### IMPLEMENT (backend → contrato → frontend)
- cambios por archivo, en orden: modelo/migración → dominio → integración util_bbdd → router → tests →
  `scripts/export_openapi.py` → `npm run gen:api` → hooks → componentes → tests → docs de usuario

### AUDIT_CODE
- salida de los agentes auditores y resultado de todos los comandos de «Comandos de desarrollo»
- `docker compose build` + `docker compose up` + `/api/health` 200
- E2E de la fase (Playwright) si se ha podido ejecutar

### VERSION
- versión MINOR nueva (`0.<fase+1>.0` hasta la 1.0), CHANGELOG, ROADMAP con la fase marcada como cerrada
- `TRACEABILITY.md` de la sesión con **Directrices para Futuras IAs**
- commit propuesto `feat(<área>): fase N — <resumen>`

## Reglas
- No adelantes historias de fases posteriores.
- Toda operación que escriba en una BD destino: rol autorizado, conexión no `read_only`, modo seco y confirmación.
- Salidas largas de validación en `build/logs/`.
