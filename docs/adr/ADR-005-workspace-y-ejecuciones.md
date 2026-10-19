# ADR-005 — Estructura del workspace y manifiesto de ejecución

- **Estado**: Aceptado (implementación en Fase 3)
- **Fecha**: 2026-10-19

## Decisión

Salidas en el volumen `workspace`, una carpeta por ejecución:

```text
/workspace/users/{user_id}/projects/{project_id}/runs/{YYYYMMDD-HHMMSS}_{operation}_{run_id}/
  run.json      # manifiesto: operación, parámetros saneados, conexiones (id/alias), versiones, tiempos, estado
  logs/run.log  # log JSON de la ejecución (incluye eventos de util_bbdd.audit vía RunAuditSink), sin secretos
  outputs/{word,excel,html,sql,markdown,graphs}/
  inputs/       # ficheros subidos (bulk)
```

- Solo **IDs** en la ruta (nunca nombres introducidos por usuarios); `run_id` es un ULID (ordenable por tiempo).
- Cada artefacto se registra en la tabla `artifacts` (ruta relativa, tipo, MIME, tamaño, SHA-256).
- Servir un fichero: `resolve()` y `is_relative_to(carpeta_del_run)`; permiso sobre el proyecto; descarga con
  `Content-Disposition: attachment`; ZIP del run generado en *streaming*.
- **Retención** configurable (días o N ejecuciones por proyecto) y **cuota** por usuario; el borrado marca el run como
  `purged` y conserva su fila y `run.json` resumido en BD.

## Consecuencias

- La UI agrupa resultados por ejecución leyendo `runs` + `artifacts`, sin recorrer el disco.
