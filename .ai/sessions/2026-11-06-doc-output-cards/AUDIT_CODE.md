# AUDIT_CODE — Tarjetas de salida de la documentación

Revisión de los cambios sin commit de la sesión (22 ficheros modificados y 6 nuevos sobre `9e1d5c5`), hecha por el
implementador tras las validaciones de [IMPLEMENT](IMPLEMENT.md). Foco: autorización, seguridad del iframe, tipado,
accesibilidad y tests.

## Corregido durante la revisión

| # | Hallazgo | Corrección |
|---|---|---|
| C1 | `backend/app/api/v1/runs.py` `_templates_applied`: una entrada de `run.json` sin `applied` (la ejecución falló antes de saberlo) contaba como **aplicada** → «Con plantilla» en una documentación fallida | Sin `applied` = no aplicada (`False`) |
| C2 | `useArtifactText` lanzaba `Error` plano: el 413/415 de la API salía como «Se ha producido un error» y se reintentaba | `ApiError` con el *problem details*; los 4xx no se reintentan (`queryClient`) |

## Autorización y seguridad

- `GET /archive?format=`: mismo `service.get_access` (miembro del proyecto) y mismo `zip_stream`/`safe_path` que el ZIP
  completo; `format` es un `Literal` (422); solo rutas de `run.artifacts`. Sin rutas del usuario (S4).
- `warnings_by_format` / `templates_applied` salen de `run.manifest` (ya visible para el miembro en `run.json`); los
  avisos son textos propios de la web, sin rutas ni secretos.
- Iframe del visor (S1): origen opaco comprobado en Chromium (`window.origin === "null"`); la CSP bloquea un
  `<script>` y un `onclick` añadidos sin limpiar a propósito; DOMPurify los quita antes (test unitario con
  `onerror`, `<script>`, `<iframe>`, `<form>`, `javascript:` y carga dentro de `foreignObject`).
- `postMessage` (T5): el puente envía solo al origen de la SPA; el padre filtra por `event.source` y formato. Test con
  `source = window` y `null`.
- `resolveLink` (T6): nunca se construye una URL de la API con texto del enlace; solo `downloadUrl(artifact.id)` de un
  artefacto registrado. Tests de `../` fuera de `docs/`, `%` mal formado, `\` y ficheros no registrados.
- Externos (D4/S3): solo `http:`/`https:` vía `new URL`, modal con la URL normalizada completa,
  `noopener,noreferrer`. Test de `javascript:`, `data:`, `file:`, `vbscript:`, `//host` y ruta absoluta.
- Sin cambios en `SITE_CSP`, la URL firmada ni `PREVIEW_CSP` (S5).

## Tipado y contrato

- `mypy --strict` y `tsc -b` limpios; `schema.d.ts` regenerado; `export_openapi.py --check` OK. Campos nuevos
  opcionales con valor por defecto: compatible con clientes y ejecuciones anteriores.

## Accesibilidad

- Cada tarjeta es una `section` con `aria-labelledby` (región con el nombre del formato); botones ZIP con nombre
  propio («Descargar ZIP de Word»).
- Árbol: `nav` con nombre, lista con `aria-current="page"`, letras con `aria-pressed`, recuento de resultados con
  `aria-live`; iframe con `title`; atrás/adelante con `aria-label`; modal con título.

## Tests añadidos

- Backend: `test_documentation_archive_by_format_preview_rules_and_page_layout` (ZIP por formato, 404, 422, vista
  previa por extensión, 415 en `catalog.json`, contrato de carpetas T2); aserciones de `warnings_by_format` y
  `templates_applied` en `test_templates.py` y `test_markdown_without_mermaid_js_warns`.
- Frontend: `documentation.test.tsx` (+3: tarjetas, formato sin ficheros, error 413 legible),
  `documentation/markdownNav.test.ts` (12), `documentation/markdownViewer.test.tsx` (7).

## Riesgos residuales (no bloquean)

- **R1** Un clic en un ancla dentro de la misma página (`#col-…`) se resuelve en el iframe y no actualiza `?md=`: el
  enlace compartido apunta a la página, no a la columna. Mejora menor.
- **R2** `file://` del ZIP HTML comprobado solo en Chromium.
- **R3** T3 sin medir en la API: la ejecución real de 630 tablas tiene 3 777 artefactos; a ~250 bytes por artefacto,
  el detalle ronda 1 MB. Si crece, paginar artefactos (fuera de alcance, ya anotado en el AUDIT_PLAN).
- **R4** El árbol depende de las carpetas de util_bbdd 5.3.0 hasta G51 (cubierto por el test de contrato).
- **R5** Las cabeceras de las páginas Markdown tienen `id` solo cuando util_bbdd los escribe (`<a id="col-…">`):
  `marked` no genera `id` en los títulos, así que un enlace a `#un-titulo` no desplaza.

## Veredicto

**APROBADO CON CONDICIONES** — condición: prueba manual con la app levantada sobre la documentación Markdown grande
del bench (tiempos del árbol y de la primera página, navegación por enlaces y anclas, ZIP Markdown publicado con
`zensical build`), prevista en el PLAN § 8 y no ejecutable aquí sin reconstruir el contenedor en uso.
