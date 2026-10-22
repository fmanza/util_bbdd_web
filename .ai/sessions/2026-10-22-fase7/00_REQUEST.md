# REQUEST

## Session metadata
- id: 2026-10-22-fase7
- fecha: 2026-10-22
- rama: develop
- skill: phase
- fase solicitada: Fase 7 completa (PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION)

## Solicitud original saneada
`/phase 7`. Inputs: alcance **completo**; rol autorizado = **permiso `can_apply_ddl` + owner**; **escritura en el
bench** permitida para las pruebas; dependencia nueva **resaltado SQL** (`highlight.js`). Tras AUDIT_PLAN:
«IMPLEMENT, pregunta lo que necesites». Respuesta durante IMPLEMENT: FK entre tipos distintos → **bloquear con
destino MariaDB/MySQL y avisar en el resto**.

## Objetivo operativo de esta sesión
- `migrate_plan` (solo lectura) con visor del plan.
- `migrate_apply` en modo seco y aplicación, con todas las garantías de la regla 6 de SHARED.

## Restricciones explícitas
- Solo `highlight.js` como dependencia nueva. Escritura en BD destino solo con permiso + owner, destino no
  `read_only`, modo seco previo y confirmación. Sin commits ni push salvo petición.

## Resultado esperado
- `util_bbdd_web` 0.8.0 con la DoD común y la de la Fase 7.
