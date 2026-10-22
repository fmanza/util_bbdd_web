# REQUEST

## Session metadata
- id: 2026-10-22-fase5
- fecha: 2026-10-22
- rama: develop
- skill: phase
- fase solicitada: Fase 5 completa (PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION)

## Solicitud original saneada
`/phase 5: documentación (Word, Excel y HTML) y grafos de relaciones.` Inputs: alcance **completo**; dependencia
nueva **renderizador de Markdown** (`marked`); sin mejoras opcionales. Tras AUDIT_PLAN: «IMPLEMENT, pregunta lo
necesario». Respuestas: sitio HTML en **origen opaco con scripts**; Oracle **aceptar con aviso** (solo el schema del
usuario).

## Objetivo operativo de esta sesión
- Ejecuciones `documentation` (Word/Excel/HTML) y `relationship_graph` (tabla o todas) en el worker.
- Sitio HTML navegable dentro de la web sin dar acceso a la sesión ni a la API.
- Formulario de lanzamiento con secciones y desplegables; descargas y galería de grafos.

## Restricciones explícitas
- Solo `marked` como dependencia nueva. Nada escribe en BD destino. Sin commits ni push salvo petición.

## Resultado esperado
- `util_bbdd_web` 0.6.0 con la DoD común y la de la Fase 5.
