# version-closure

Cierre de versión, fase o sesión.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/prompts/version_closure.prompt.md` — inputs, contrato de salida y reglas (manda sobre este fichero)
2. Agentes: Version Closer (`.github/agents/`)

## Reglas de ejecución

- Si falta algún input del prompt, DETENTE y aclara antes de emitir PLAN.
- En flujos con IMPLEMENT, detente tras AUDIT_PLAN y espera aprobación explícita.

## Ejemplo de entrada

```text
/version-closure

Cambios: Fase 1 — identidad y multiusuario
Versión: v0.2.0
Fase: 1
Sesión: .ai/sessions/2026-10-25-fase1/
```
