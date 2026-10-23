# REQUEST

## Session metadata
- id: 2026-10-23-fase9
- fecha: 2026-10-23
- rama: develop
- skill: phase
- fase solicitada: Fase 9 completa (PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION)

## Solicitud original saneada
`/phase 9`. Inputs: **reutilizar `can_write_data`** (etiqueta «Puede escribir datos») + owner; operaciones **insert,
update y delete**, con confirmación extra de las filas afectadas en update/delete; subida **`multipart/form-data`**
(dependencia nueva `python-multipart`); alcance **completo** (plan paralelo y escritura real en el bench). Tras
AUDIT_PLAN: «IMPLEMENT, pregunta lo que necesites».

## Objetivo operativo de esta sesión
- Subidas CSV/Excel validadas, `bulk_preview` (modo seco con SQL generado) y `bulk_apply` con las garantías de la
  regla 6 de SHARED (ADR-010).

## Restricciones explícitas
- Una dependencia nueva (`python-multipart>=0.0.32`). Escritura en BD destino solo con permiso + owner, destino no
  `read_only`, vista previa reciente y confirmación. Sin commits ni push salvo petición.

## Resultado esperado
- `util_bbdd_web` 0.10.0 con la DoD común y la de la Fase 9.
