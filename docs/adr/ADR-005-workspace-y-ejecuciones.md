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
  `runs.manifest` (copia de `run.json`). Desde ADR-012, cuota y retención se administran en la web (las variables son
  el valor por defecto) y hay una purga por cuota opcional.
- `RunAuditSink` (`integrations/util_bbdd/audit_sink.py`) cumple `util_bbdd.audit.AuditSink` y escribe en `run.log`
  **sin** `AuditEvent.message` (puede llevar valores de clave). Lo usarán las fases 7–9.

## Enmienda 2026-11-07 (1.14.0): eliminar ejecuciones desde administración

El borrado deja de ser solo la purga (`purged`, conservando fila y `manifest`): un admin puede **eliminar** una
ejecución terminada o todas las terminadas de un proyecto (*Administración → Todas las ejecuciones*). Se borran la
fila, sus artefactos y su carpeta, y desaparece del historial; la auditoría (`run.delete`, `project.runs_delete`)
guarda su resumen. Una activa o un volcado con constraints sin restaurar no se elimina (409; el borrado de un proyecto
los omite y dice cuántos). Esa lista solo muestra metadatos (ni `params`, ni mensajes, ni artefactos), y una
ejecución relanzada desde otra eliminada lo indica con `RunDetailOut.relaunched_from_exists`.

## Enmienda (2026-11-24): el creador puede cambiar

La carpeta del proyecto sigue colgando de `projects.owner_id`, pero desde la transferencia de usuarios
([ADR-013](ADR-013-borrado-de-usuarios.md), enmienda) `owner_id` puede cambiar: la carpeta se mueve y se reescriben
las rutas guardadas (`runs.workspace_path`, `uploads.path`, `document_templates.path`). Toda ruta nueva bajo
`users/<owner_id>/projects/<id>` que se guarde en la base de datos debe añadirse a esa reescritura.
