# REQUEST

## Session metadata
- id: 2026-10-22-fase4
- fecha: 2026-10-22
- rama: develop
- skill: phase
- fase solicitada: Fase 4 completa (PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION)

## Solicitud original saneada
`/phase 4: explorador de metadatos, con árbol schema → tablas, detalle de tabla, queries nombradas y SQL libre
restringido`. Inputs: SQL libre con **permiso por usuario** (más editor del proyecto); dependencia `sqlglot` directa;
alcance completo sin mejoras. Tras AUDIT_PLAN: «IMPLEMENT, pregunta lo necesario». Respuestas: queries nombradas con
**CRUD en la web**; SQL Server **permitido con aviso**; errores del SQL libre **con el mensaje del motor recortado**.

## Objetivo operativo de esta sesión
- Explorador por conexión: schemas, árbol, detalle de tabla, DDL y caché del snapshot.
- Queries nombradas gestionadas por admins y ejecutadas con util_bbdd con parámetros seguros.
- SQL libre de solo lectura con defensa en capas, auditado.

## Restricciones explícitas
- Solo `sqlglot` como dependencia nueva. Nada escribe en BD destino. Sin commits ni push salvo petición.

## Resultado esperado
- `util_bbdd_web` 0.5.0 con la DoD común y la de la Fase 4.
