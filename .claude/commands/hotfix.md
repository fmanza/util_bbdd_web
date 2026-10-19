# hotfix

Bug P1/P2: RCA y fix mínimo, sin refactorizar.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/prompts/hotfix.prompt.md` — inputs, contrato de salida y reglas (manda sobre este fichero)
2. Agentes: Hotfix Responder → Code Auditor → Version Closer (`.github/agents/`)

## Reglas de ejecución

- Si falta algún input del prompt, DETENTE y aclara antes de emitir PLAN.
- En flujos con IMPLEMENT, detente tras AUDIT_PLAN y espera aprobación explícita.

## Ejemplo de entrada

```text
/hotfix

Bug: la descarga ZIP de una ejecución devuelve 500
Dónde: GET /api/v1/runs/{id}/archive
Síntomas: log JSON con exc_type=FileNotFoundError
Supuesto: la retención borró la carpeta y el run sigue listado
```
