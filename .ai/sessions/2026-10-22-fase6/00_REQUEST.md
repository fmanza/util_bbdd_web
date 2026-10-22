# REQUEST

## Session metadata
- id: 2026-10-22-fase6
- fecha: 2026-10-22
- rama: develop
- skill: phase
- fase solicitada: Fase 6 completa (PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION)

## Solicitud original saneada
`/phase 6`. Inputs: alcance **completo**; mejora opcional **incluida** (comparar dos ejecuciones `compare`);
dependencia nueva **visor de diff de texto** (`diff`). Tras AUDIT_PLAN: «IMPLEMENT, pregunta lo que necesites».
Respuestas: Mermaid del CDN **bloqueado**; al ver que eso rompía el script del informe, **sustituto local** de
Mermaid.

## Objetivo operativo de esta sesión
- Ejecución `compare` con diff guardado e informes de util_bbdd.
- Visor del diff navegable y evolución entre dos comparaciones.

## Restricciones explícitas
- Solo `diff` como dependencia nueva. Nada escribe en BD destino (el script SQL solo se genera). Sin commits ni push
  salvo petición.

## Resultado esperado
- `util_bbdd_web` 0.7.0 con la DoD común y la de la Fase 6.
