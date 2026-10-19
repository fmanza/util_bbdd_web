# tech-debt

Deuda técnica priorizada.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/prompts/tech_debt.prompt.md` — inputs, contrato de salida y reglas (manda sobre este fichero)
2. Agentes: Plan Architect (→ Feature Implementer → Code Auditor → Version Closer si se autoriza IMPLEMENT) (`.github/agents/`)

## Reglas de ejecución

- Si falta algún input del prompt, DETENTE y aclara antes de emitir PLAN.
- En flujos con IMPLEMENT, detente tras AUDIT_PLAN y espera aprobación explícita.

## Ejemplo de entrada

```text
/tech-debt

Área: frontend/
Síntomas: bundle > 500 kB
Versión: 0.1.0 (develop)
Scope: solo análisis
Compatibilidad: sin romper la API HTTP
```
