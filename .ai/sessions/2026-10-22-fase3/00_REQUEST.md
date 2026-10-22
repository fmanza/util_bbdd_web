# REQUEST

## Session metadata
- id: 2026-10-22-fase3
- fecha: 2026-10-20 → 2026-10-22
- rama: develop
- skill: phase
- fase solicitada: Fase 3 completa (PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION)

## Solicitud original saneada
`/phase 3: proyectos con miembros, motor de ejecuciones con worker y un subproceso por job, SSE para el progreso y
workspace por ejecución.` Inputs aclarados: alcance **completo** del ROADMAP; dependencias nuevas: **ninguna**;
mejoras opcionales: **no**. Tras AUDIT_PLAN: «IMPLEMENT» (acepta las desviaciones 1–4). A mitad de IMPLEMENT: «continúa;
puedes continuar en la nube» → se continúa en local (cambios sin commit, Docker y bench locales).

## Objetivo operativo de esta sesión
- Proyectos con miembros por rol y conexiones con alias.
- Cola sobre `runs`, worker con un subproceso por job, cancelación, timeout y recuperación.
- Progreso por SSE, workspace por ejecución con `run.json`, artefactos con vista previa segura y ZIP.
- Retención, cuota, `RunAuditSink` y job `noop`; frontend y E2E.

## Restricciones explícitas
- Sin dependencias nuevas. Sin escritura en BD destino. Sin commits ni push salvo petición.

## Resultado esperado
- `util_bbdd_web` 0.4.0 con la DoD común y la de la Fase 3.
