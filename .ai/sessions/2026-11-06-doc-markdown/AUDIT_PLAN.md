# AUDIT_PLAN — Documentación Markdown (util_bbdd 5.3.0)

Contraste del [PLAN](PLAN.md) con el código de la web (v1.10.1, `f521610`) y util_bbdd `v5.3.0`.

## Comprobación del traspaso

| # | Traspaso | Estado en el código | Ajuste del PLAN |
|---|---|---|---|
| W-1 | Subir a 5.3.0 | `pyproject.toml:19,57` en 5.2.0 por URL de release | **Bloqueado**: la release v5.3.0 no tiene wheel |
| W-2 | `_FORMAT_DIRS` | `documentation.py:42`, confirmado | — |
| W-3 | Mover la carpeta | `documentation.py:359-372`, confirmado: el `iterdir() if is_file()` perdería `docs/` | — |
| W-4 | `mermaid_js` local | `settings.mermaid_js` (`config.py:104`), imagen con `/app/vendor/mermaid.min.js` | Si no existe el fichero: aviso, no error |
| W-5 | Opciones | `DocumentationParams` (`operations.py:71`); formulario genérico por `ubw_group` | Markdown **desactivado por defecto**; grupo visible solo con la casilla |
| W-5 | — | **No estaba en el traspaso**: `generate_documentation` exige `dot` si `graphs`, aunque solo se pida Markdown | Condición por formatos Word/HTML |
| W-6 | Subida `.toml`/`.json` | Plantillas ADR-011 ya resuelven ámbito, permisos, cuota, SHA-256 y copia a `inputs/` | Tipo `trace` en `document_templates`, sin migración |
| W-6 | «Mensaje tal cual» | Los mensajes llevan la ruta absoluta (`_trace.py:105,111`, `_changes.py:93`) | **No tal cual**: rutas sustituidas por el nombre mostrado |
| W-7 | Pasar la carpeta anterior | Acoplaría el run a la carpeta (y la retención) de otro | Se copia solo su `catalog.json` a `inputs/previous/` |
| W-7 | Visor de diferencias | `load_diff` (`diff.py:33`) solo `compare` + `schema_diff.json` | Se amplía a `documentation` + `changes.json`; evolución sin cambios |
| W-8 | Vista previa | `ArtifactBrowser` ya pinta `.md` con Mermaid y `stripMermaidConfig` | Solo quitar el front matter; sitio Zensical fuera de alcance |
| W-9 | ZIP | `scan_artifacts` recorre `outputs/**` | Sin cambios |
| W-10 | ROADMAP | — | ROADMAP + G49 + adenda ADR-011 |

## Riesgos funcionales

- **F1** Ejecuciones existentes: con `markdown=false` por defecto, `build_imprimir` no añade el bloque y la salida
  Word/Excel/HTML no cambia. Test de regresión de `build_imprimir` sin Markdown.
- **F2** La profundidad efectiva es `min(graph_depth, markdown_diagram_depth)`: un usuario con `graph_depth=3` y el
  tope por defecto (2) ve el aviso `!!! warning` en las páginas. Ayuda del campo lo explica.
- **F3** Ejecución anterior de una documentación sin Markdown o purgada: se rechaza al lanzar (422), no en el job.
- **F4** Front matter JSON de una línea: `marked` lo pinta como `<hr>` + texto; se quita en la vista previa (no en
  el fichero).
- **F5** Enlaces relativos entre páginas en la vista previa no navegan (el navegador de artefactos no es un sitio):
  aceptado; el sitio completo llega con la mejora opcional Zensical.

## Riesgos técnicos

- **T1 (bloqueante)** Wheel 5.3.0 ausente en la release. `uv lock` fallaría.
- **T2** Volumen de artefactos: miles de filas por run (cada una con SHA-256 al cerrar) y un navegador largo.
  `scan_artifacts` ya hashea en streaming; el navegador ya agrupa por tipo. **Condición:** medir con un schema de
  ≥ 500 tablas en la prueba de integración (tiempo de cierre y respuesta de `GET /runs/{id}`); si el detalle se
  degrada, paginar artefactos en otro cambio, no en este.
- **T3** `mermaid.min.js` (~3 MB) por run cuenta para la cuota (ADR-012). Aceptado y documentado en la guía.
- **T4** Mapa con errores de esquema descubierto tras conectar (validación en el constructor, dentro de
  `with SyncDatabaseManager`). Aceptable; G49 lo resolvería al subir.
- **T5** `kind String(8)`: `"trace"` cabe; `"trace_map"` no. Fijado `trace`.
- **T6** Tipo de parámetro nuevo `run` en el formulario genérico: es la única pieza de UI realmente nueva. El listado
  de runs por proyecto y operación está **PENDIENTE DE VERIFICAR**.

## Riesgos de seguridad

- **S1 (Regla 5 / ASVS 7.4)** Rutas del servidor en mensajes de error → `public_message` + test que comprueba que
  ni `run_dir` ni `workspace` aparecen en `run.json`, `logs/run.log` ni el `error` del run.
- **S2 (A01, IDOR)** `markdown_previous_run` de otro proyecto o de una ejecución sin acceso: comprobación en el
  servicio con el mismo patrón que `preview_run` de volcado y carga; test API con un run de otro proyecto (404/422
  indistinguible para no revelar su existencia).
- **S3** Subida del mapa: tamaño acotado antes de leer (rechazo temprano de v1.10.1), solo `.toml`/`.json`, UTF-8,
  nombre mostrado saneado (`display_name`), guardado con id (nunca con el nombre del usuario).
- **S4 (XSS)** El Markdown generado incluye comentarios de la BD y textos del mapa: se renderiza con el saneado actual
  del `ArtifactBrowser` y Mermaid `securityLevel: strict`; G46 resuelto en 5.2.0 y `stripMermaidConfig` como defensa.
  Sin `dangerouslySetInnerHTML` nuevo.
- **S5** Sin escritura en BD destino: la operación solo lee el catálogo (regla 6 no aplica).
- **S6** `mkdocs.yml` y `llms*.txt` descargados no se ejecutan en el servidor.

## Simplificaciones

- Mapa de trazabilidad como **tipo de plantilla** en vez de entidad nueva: sin migración, sin endpoints nuevos.
- `previous` = copia de `catalog.json`, no la carpeta: sin acoplamiento entre runs.
- Visor de diferencias reutilizado tal cual (`read_diff` ya lee `SchemaDiff.to_dict()`).
- Sin sitio Zensical en el job (W-8 opcional) ni cambios en el ZIP (W-9).
- Sin opciones avanzadas en el formulario (`index_page_size`, `front_matter`, `column_anchors`, `catalog_json`,
  `llms_*`, `mkdocs_yml`): valores por defecto de util_bbdd.

## Decisiones que necesitan confirmación

1. **Mapa inválido**: ¿falla la ejecución (`invalid_trace_map`, propuesta) o se genera sin mapa con un aviso, como
   las plantillas Word/Excel?
2. **Alcance de esta entrega**: ¿A–C + F + G (Markdown básico) primero y D–E (mapa y comparación) en un segundo
   cambio, o todo junto en 1.11.0? Propuesta: todo junto, implementado por bloques A→G con la suite verde entre
   bloques.

## Verdict

**`GO_CONDICIONAL`**

Condiciones para pasar a IMPLEMENT:

1. Wheel `util_bbdd-5.3.0-py3-none-any.whl` (y su `.sha256`) publicado en la release v5.3.0 (T1).
2. Respuesta a las dos decisiones anteriores.
3. Verificar el filtrado de `GET /api/v1/runs` por proyecto y operación antes del bloque E (T6).

Condiciones dentro de IMPLEMENT: saneado de rutas con test (S1), control de acceso de `markdown_previous_run` con
test (S2) y medición del volumen de artefactos (T2).
