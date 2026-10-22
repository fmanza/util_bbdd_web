# ADR-005 — Estructura del workspace y manifiesto de ejecución

- **Estado**: Aceptado (implementado en la Fase 3, 0.4.0)
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

## Notas de implementación (Fase 3)

- `app/workspace/layout.py` (solo depende de `core`): `run_relative_path` (solo IDs y la operación del catálogo),
  `safe_path` (`resolve` + `is_relative_to`, rechaza absolutas, `..` y la propia raíz), escritura atómica de `run.json`,
  `scan_artifacts` (tipo, MIME, tamaño, SHA-256; ignora `inputs/`, temporales y enlaces) y `zip_stream` (ZIP por
  trozos sin fichero temporal).
- La carpeta del usuario es la del **creador** del proyecto (`projects.owner_id`), aunque luego cambien los owners.
- Vistas previas: HTML y SVG con `Content-Security-Policy: sandbox; default-src 'none'…` y en `iframe sandbox=""`
  (verificado en E2E: el `<script>` del HTML de ejemplo no se ejecuta); Markdown, SQL, log y `run.json` como
  `text/plain`. Descargas con `Content-Disposition: attachment` y `nosniff`.
- **Retención** (`UBW_RUN_RETENTION_DAYS`, `UBW_RUN_RETENTION_PER_PROJECT`) al arrancar el worker y cada hora;
  **purga manual** (`DELETE /runs/{id}`) para liberar cuota (`UBW_USER_QUOTA_MB`). Un run purgado conserva la fila y
  `runs.manifest` (copia de `run.json`).
- `RunAuditSink` (`integrations/util_bbdd/audit_sink.py`) cumple `util_bbdd.audit.AuditSink` y escribe en `run.log`
  **sin** `AuditEvent.message` (puede llevar valores de clave). Lo usarán las fases 7–9.
