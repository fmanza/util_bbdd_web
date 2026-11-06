# PLAN — Tarjetas de salida de la documentación (Word, Excel, HTML, Markdown)

Sesión `2026-11-06-doc-output-cards` · web 1.11.0 · util_bbdd 5.3.0 · Fase: PLAN (sin implementar).

## 0. Decisiones del usuario (2026-11-06)

| # | Decisión |
|---|---|
| D1 | Visor Markdown: **M2** (árbol + buscador + iframe aislado con puente de navegación). M4 queda como mejora opcional del ROADMAP |
| D2 | Pasos 1 y 2 del roadmap en **una sola versión**: web 1.12.0 |
| D3 | **G50 y G51 registrados** en `docs/plan/UTIL_BBDD_GAPS.md` (abiertos) |
| D4 | Enlaces externos (`http`/`https`, p. ej. del mapa de trazabilidad): se abren **en otra pestaña tras confirmación** (modal «Vas a salir de la aplicación» con la URL completa); cualquier otro esquema se ignora |

## 1. Estado actual (verificado en el código)

| Pieza | Dónde | Comportamiento hoy |
|---|---|---|
| Resultados destacados | `frontend/src/features/runs/RunOutputs.tsx` | **Una** tarjeta «Documentación» que mezcla botones de Word/Excel (uno por fichero, `DEFAULT_DOCUMENT_KINDS`) y el iframe del sitio HTML (`site_url`). Markdown: otra tarjeta con solo un texto (`markdownHint`) que remite a «Artefactos». |
| Navegador de artefactos | `ArtifactBrowser.tsx` | Lista plana de **todos** los artefactos (oculta solo los del sitio HTML, `isSiteFile`). Con Markdown son cientos o miles de filas (un `.md` por objeto + índices por letra). |
| Vista previa Markdown | `ArtifactBrowser.tsx` `MarkdownPreview` | `marked` → Mermaid a SVG en la SPA → `iframe sandbox=""` con `srcDoc` y CSP sin red. |
| Clasificación | `backend/app/workspace/layout.py:140` `_kind` | El tipo sale de la carpeta: **todo** lo que hay bajo `outputs/markdown/` es `markdown` (también `mermaid.min.js`, `catalog.json`, `llms*.txt`, `mkdocs.yml`, `manifest.json`). |
| Vista previa (API) | `backend/app/api/v1/runs.py:75` `_previewable` | Por tipo: `markdown` ∈ `TEXT_KINDS` → todos esos ficheros son «previsualizables»; límite `PREVIEW_MAX_BYTES` = 2 MB → 413. |
| ZIP | `runs.py:513` `download_archive` | Un único ZIP con **todos** los artefactos del run; no hay ZIP por formato. |

### 1.1 Causa de los errores de la vista Markdown

1. **`mermaid.min.js`**: 5,5 MB (`mermaid@12`, el de `UBW_MERMAID_JS`) > 2 MB → `PreviewTooLargeError` (413). Aunque
   cupiera, se pasaría a `marked` como si fuera Markdown.
2. **`catalog.json` y `llms-full.txt`**: el mismo error de clasificación. Si pasan de 2 MB (esquemas medianos), 413; si
   no, `marked` pinta un JSON como un párrafo, y `llms-full.txt` (todas las páginas juntas) dibuja en serie **todos** los
   diagramas Mermaid del esquema, lo que puede tardar mucho o quedarse colgado. *Pendiente de verificar con una
   ejecución real qué mensaje exacto ve el usuario en cada uno.*
3. **Enlaces**: util_bbdd genera enlaces relativos (`md_link`, p. ej. `pedidos.md`, `../views/v.md#col-id`). Dentro de un
   `iframe srcDoc` con `sandbox=""` esa ruta se resuelve contra `about:srcdoc` y el iframe navega a una página inexistente
   (o bloqueada). Ya se aceptó como limitación en la sesión `2026-11-06-doc-markdown` (AUDIT_PLAN F5), a la espera del
   sitio Zensical (ROADMAP, «Mejoras opcionales»).

## 2. Objetivo

En una ejecución `documentation`, una **tarjeta por formato generado** (solo los de `params.formats`), con la misma
estructura: título, descripción del formato, recuento y tamaño, avisos de ese formato, acciones (ZIP y, si procede,
ver). La comparación (`compare`) y el grafo (`relationship_graph`) no cambian.

| Tarjeta | Contenido | Acciones | Vista previa |
|---|---|---|---|
| **Word** | Lista de `.docx` (varios si `tablas_por_documento`), tamaño, «con plantilla» si se aplicó | Descarga de cada documento + **ZIP Word** | No |
| **Excel** | El `.xlsx` (tamaño, «con plantilla») | Descarga + **ZIP Excel** | No |
| **HTML** | Sitio navegable (iframe actual, `site_url`, ADR-007) | «Abrir en pestaña» + **ZIP HTML** (abrir `index.html` sin conexión) | Sí, la actual |
| **Markdown** | Visor propio (§ 4) | **ZIP Markdown** (publicable con Zensical/MkDocs) + descarga de `catalog.json`, `llms.txt`, `llms-full.txt`, `mkdocs.yml` como «Ficheros auxiliares» | Sí, solo `.md` |

## 3. Cambios por capa

### A — Backend: ZIP por formato

- `GET /api/v1/runs/{id}/archive?format=word|excel|html|markdown` (opcional; sin él, el ZIP completo de hoy). Filtra
  `run.artifacts` por `kind` y nombra `"<prefijo>_<format>.zip"`. Reutiliza `zip_stream` (streaming, `safe_path`).
- `format` validado con un `Literal` (422 si no); 404 si no hay artefactos de ese tipo.
- OpenAPI regenerado (`openapi/`) y tipos del frontend (`api` generado).

### B — Backend: vista previa por extensión, no solo por tipo

- `_previewable`: en `markdown`, solo `.md` (y `.txt` hasta 2 MB como texto plano, sin `marked`, si se quiere ver
  `llms.txt`). `.js`, `.json`, `.yml` → `previewable=false` («descárgalo»), sin tocar el tipo guardado.
- **No** se cambia `_kind` ni la tabla `artifacts`: las ejecuciones antiguas siguen bien sin migración de datos.
- Opcional: `ArtifactOut.role` calculado (`page | asset | aux`) para que el frontend no repita la regla.

### C — Frontend: tarjetas

- `RunOutputs.tsx` se divide: `DocumentationOutputs` (solo `documentation`) con `FormatCard` común
  (`WordCard`, `ExcelCard`, `HtmlCard`, `MarkdownCard`) y la rama actual para `compare` / `relationship_graph`.
- Textos en `i18n/es/features.json` (`runs.outputs.formats.<f>.title|description`).
- Avisos: los de `run.warnings` que correspondan a cada formato (plantilla descartada, Mermaid local ausente) se
  muestran en su tarjeta. *Hoy son texto libre: o se filtran por palabra, o el manifiesto guarda `warnings` por formato
  (cambio pequeño en `jobs/operations/documentation.py`; preferible).*
- «Con plantilla»: `templates_applied` ya está en el resultado del job; exponerlo en `RunDetailOut` (campo opcional).

### D — Frontend: navegador de artefactos sin el scroll de Markdown

- `ArtifactBrowser` oculta `outputs/markdown/documentacion/**` como ya oculta el sitio HTML (`isSiteFile` →
  `isSiteFile || isMarkdownDocFile`) y muestra «N ficheros de la documentación Markdown: ver en su tarjeta». Así la
  lista vuelve a tener una decena de filas.

## 4. Visor Markdown — alternativas

| # | Alternativa | Navegación | Coste | Seguridad |
|---|---|---|---|---|
| **M1** | Árbol + buscador + vista previa actual (sin enlaces) | Solo desde el árbol | Bajo | Igual que hoy |
| **M2 (recomendada)** | Árbol + buscador + iframe con **puente de navegación**: el HTML de `marked` se limpia con DOMPurify, el iframe pasa a `sandbox="allow-scripts"` (sin `allow-same-origin`: origen opaco) con CSP `script-src 'nonce-…'; connect-src 'none'`, y un script mínimo con nonce intercepta los clics en enlaces relativos y hace `postMessage({path, hash})` al padre, que resuelve la ruta y carga la página | Enlaces entre páginas, anclas (`#col-…`) y atrás/adelante (historial propio) | Medio | Origen opaco + CSP sin red + DOMPurify; el padre valida `event.source` |
| M3 | Renderizar en el DOM de la SPA (sin iframe) con DOMPurify e interceptar clics en React | Completa | Medio | Contenido de la BD en el origen de la SPA: rompe el criterio de aislamiento de ADR-007 |
| M4 | `zensical build` en el job y servir el sitio por URL firmada, como el HTML | La del sitio (buscador incluido) | Alto: Zensical en la imagen de runtime, ADR nuevo, tiempo y disco por run | La de ADR-007 |

**Propuesta: M2 ahora; M4 sigue como mejora opcional en el ROADMAP.**

Diseño de M2:

- **Árbol** (columna izquierda, con scroll propio y altura fija): Portada · Tablas · Vistas · Rutinas · Base de datos
  · Cambios / Trazabilidad (si existen). Se construye con las rutas de los artefactos (`docs/tables/*.md`…), que ya
  están en `run.artifacts`; los `index-<letra>.md` de util_bbdd dan el índice por letra sin cargar nada más.
- **Buscador** por nombre de objeto (filtro en el cliente sobre las rutas; opcional, con `catalog.json` para buscar
  también por columna: se descarga una vez si pesa ≤ 2 MB).
- **Lista virtualizada** o paginada por letra para esquemas de miles de objetos (sin dependencias nuevas: paginación
  por letra con `SegmentedControl`/`Pagination` de Mantine).
- **Resolución de enlaces** en el padre: ruta relativa a la página actual → artefacto registrado (búsqueda por
  `path`) → si es `.md`, se carga; si es `catalog.json`, `llms*.txt` u otro, se ofrece la descarga; si es `http(s)`, modal de
  confirmación con la URL y `window.open(url, '_blank', 'noopener,noreferrer')` (D4); otro esquema, se ignora; si no
  existe, aviso.
- Las páginas de la raíz de `docs/` (`index.md`, `traceability.md`, `changes.md`) van arriba del árbol.
- **URL compartible**: la página abierta en el query string (`?md=tables/pedidos.md#col-id`).
- **Mermaid**: se sigue dibujando en la SPA (`renderMermaidBlocks`); `mermaid.min.js` del run **no** se usa en el visor
  (solo en el sitio publicado desde el ZIP).

## 5. Gap con util_bbdd

No hay ningún hueco que bloquee el trabajo: todo se puede hacer en la web. Candidatos para `UTIL_BBDD_GAPS.md`:

| Id | Hueco | Impacto en la web | Prioridad |
|---|---|---|---|
| G50 (registrado) | `markdown.mermaid_js` solo admite copiar el fichero: cada run guarda 5,5 MB de `mermaid.min.js`. Falta una opción para referenciarlo (ruta o URL relativa en `extra_javascript` sin copiar) | Cuota y retención: 5,5 MB por documentación Markdown | Baja |
| G51 (registrado) | `catalog.json` no lista las páginas auxiliares (índices, `database/*`, cambios, trazabilidad) y la `nav` de `mkdocs.yml` es corta y en YAML. Un `nav.json` (o una sección `pages` en `manifest.json`) daría el árbol sin deducirlo de las rutas | El árbol depende de la estructura de carpetas de util_bbdd (`docs/tables/…`); un cambio de esa estructura lo rompería en silencio | Baja; mientras tanto, test de contrato con las rutas |
| G49 | Validador público del mapa de trazabilidad | Ya abierto; no afecta a esta sesión | — |

## 6. Roadmap propuesto

| Paso | Contenido | Versión |
|---|---|---|
| 1 | A + B + C + D: tarjetas por formato, ZIP por formato, vista previa solo de `.md`, navegador sin la carpeta Markdown | web 1.12.0 (MINOR: endpoint con parámetro nuevo, compatible) |
| 2 | Visor Markdown M2 (árbol, buscador, puente de navegación, URL compartible, enlaces externos con confirmación) | web 1.12.0 (D2: misma versión; dos commits `feat`, uno por paso) |
| 3 | G50/G51 en util_bbdd, si se aceptan | util_bbdd 5.4.0 + wheel en `vendor/wheels/` |
| 4 | M4 (sitio Zensical en el job) | Opcional, ADR nuevo |

## 7. Ficheros afectados (estimación)

- Backend: `api/v1/runs.py` (`download_archive`, `_previewable`, `_detail`), `api/v1/schemas_projects.py`
  (`RunDetailOut.templates_applied`, `ArtifactOut.role` opcional), `jobs/operations/documentation.py` (avisos por formato),
  tests `backend/tests/…/test_runs*.py`, `openapi/`.
- Frontend: `RunOutputs.tsx` (división), nuevos `documentation/FormatCard.tsx`, `documentation/MarkdownViewer.tsx`,
  `documentation/markdownNav.ts` (resolución de rutas, pura y testeable), `ArtifactBrowser.tsx`, `useRuns.ts`
  (`archiveUrl(runId, format?)`), `i18n/es/features.json`, tests `documentation.test.tsx`, `markdown.test.tsx`.
- Docs: `docs/guides/documentacion.md` (tarjetas, ZIP por formato, visor), ADR-007 (enmienda: iframe Markdown con
  `allow-scripts` y nonce), `CHANGELOG.md`, `ROADMAP.md`, `UTIL_BBDD_GAPS.md` (G50/G51 si se aceptan).

## 8. Pruebas previstas

- Backend: ZIP por formato (contenido, nombre, 404 sin artefactos, 422 con formato inválido, sin path traversal);
  `previewable` falso para `.js`/`.json`/`.yml` bajo `markdown`; ejecución antigua sin cambios.
- Frontend: una tarjeta por formato pedido y ninguna de los no pedidos; Word con varios documentos; el navegador oculta
  la carpeta Markdown; `markdownNav` (relativas, `../`, anclas, inexistentes, externas, `catalog.json`); el visor ignora
  mensajes de otro `source`.
- Manual (bench): documentación Markdown de un schema grande (Oracle o MariaDB del bench) → tiempos del árbol y de la
  primera página; navegación por enlaces y anclas; ZIP Markdown publicado con `zensical build`.
