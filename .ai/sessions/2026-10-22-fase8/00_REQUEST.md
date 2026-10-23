# REQUEST

## Session metadata
- id: 2026-10-22-fase8
- fecha: 2026-10-22 (cierre el 2026-10-23)
- rama: develop
- skill: phase
- fase solicitada: Fase 8 completa (PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION)

## Solicitud original saneada
`/phase 8 pregunta lo que necesites`. Inputs: permiso nuevo **`can_write_data`** + owner; vaciar el destino
**permitido con confirmación extra**; volcado en curso **no cancelable**; alcance **completo** + **aislar rechazos** +
**repartir el bundle**. Tras AUDIT_PLAN: «IMPLEMENT, pregunta lo que necesites». Durante IMPLEMENT, al medir que el
bundle lo dominan las librerías (no las traducciones): **vendors + i18n por ruta**.

## Objetivo operativo de esta sesión
- `dump_preview` (modo seco) y `dump_apply` con las garantías de la regla 6 de SHARED (ADR-009).
- Bundle principal por debajo del aviso de Vite.

## Restricciones explícitas
- Sin dependencias nuevas. Escritura en BD destino solo con permiso + owner, destino no `read_only`, vista previa
  reciente y confirmación. Sin commits ni push salvo petición.

## Resultado esperado
- `util_bbdd_web` 0.9.0 con la DoD común y la de la Fase 8.
