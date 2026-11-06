# PLAN — Ola 11: G50 (Mermaid referenciado) y G51 (índice de páginas de la documentación Markdown)

Sesión `2026-11-06-gaps-g50-g51` · web 1.12.0 (`39cf285`) · util_bbdd 5.3.0 (`2841111d`, repo origen leído en solo
lectura) · Fase: PLAN (sin implementar). Decisiones D11-1 a D11-4 en [00_REQUEST.md](00_REQUEST.md).

Sigue las reglas de [UTIL_BBDD_GAPS_PLAN.md](../../../docs/plan/UTIL_BBDD_GAPS_PLAN.md) §1: la web no parchea
util_bbdd; una fase = un commit = un repositorio (`U-` / `W-`); una release de util_bbdd por ola; la web sube de
versión en su propio commit.

## 1. Estado verificado

### G50 — `mermaid.min.js` copiado en cada generación

| Pieza | Dónde (util_bbdd 5.3.0) | Hoy |
|---|---|---|
| Opción | `print_config_manager.py:93` (defecto `None`), `:276` (normaliza ruta), `:466` (resuelve) | `markdown.mermaid_js`: ruta a un fichero |
| Validación | `documentation_orchestrator.py:126-134` `_check_markdown_files` | Debe ser un fichero, si no `DocumentationConfigError` |
| Escritura | `markdown_generator.py:380-382` | `writer.copy("docs/assets/javascripts/mermaid.min.js", …)` (`MERMAID_JS_PATH`, `_site.py:14`) |
| `mkdocs.yml` | `_site.py:17-51` `mkdocs_yml(..., with_mermaid_js)` | Con Mermaid local: `theme.font: false` y `extra_javascript: [assets/javascripts/mermaid.min.js]`; sin él, nada (Material carga Mermaid de unpkg) |
| Manifiesto | `_writer.py:69-85` | El fichero copiado entra en `manifest.json` → `files` con su hash |

| Pieza | Dónde (web 1.12.0) | Hoy |
|---|---|---|
| Ajuste | `core/config.py:104` `mermaid_js` (`UBW_MERMAID_JS`, imagen: `/app/vendor/mermaid.min.js`, `mermaid@12.2.0`) | También lo usa el informe HTML de comparación (incrustado; fuera de alcance) |
| Job | `jobs/operations/documentation.py` `_mermaid_js` → `MarkdownInputs.mermaid_js` → `integrations/util_bbdd/documentation.py:307-313` `_markdown_block` | Se pasa la ruta; util_bbdd copia **5,5 MB por ejecución** (cuenta en cuota y retención) |
| ZIP | `api/v1/runs.py` `download_archive` → `workspace/layout.py:216` `zip_stream(directory, relatives, prefix)` | Solo artefactos registrados |
| Visor | `documentation/MarkdownViewer.tsx` | No usa el Mermaid del run (dibuja con el de la SPA) |

### G51 — sin índice de todas las páginas

- `catalog.json` (ADR-006 de util_bbdd, `_catalog.py`) lista solo **objetos** (`kind`, `name`, `id`, `path`…), no los
  índices (`tables/index.md`, `index-<letra>[-n].md`, `_site_pages.py:64-84`), `database/*.md`, `traceability.md` ni
  `changes.md`; además pesa 3,6 MB en un schema de 630 tablas.
- `mkdocs.yml` → `nav` es corta (portada, índices de sección, trazabilidad, cambios) y en YAML.
- `manifest.json` (`_writer.py:92-119`, `format` `util_bbdd.doc.markdown`, `format_version` 1) tiene `files` (ruta →
  hash) de **todos** los ficheros, sin título ni tipo.
- La web deduce el árbol de las rutas (`documentation/markdownNav.ts` `buildPages`): etiquetas = *slug* del fichero
  (`acm-agenda`, no `ACM_AGENDA`), secciones por carpeta. Lo protege el test de contrato
  `test_documentation_archive_by_format_preview_rules_and_page_layout` (T2 de la sesión anterior).

## 2. Objetivo

1. **G50**: una documentación Markdown deja de guardar su `mermaid.min.js`; el ZIP Markdown (y el completo) lo
   sigue llevando, así que la carpeta se publica sin Internet igual que hoy.
2. **G51**: util_bbdd publica un índice máquina-legible de todas las páginas; el visor de la web lo usa para el árbol
   (nombres reales y títulos) y deja de depender de la estructura de carpetas, salvo en ejecuciones antiguas.

## 3. Fases en util_bbdd (ola 11 → util_bbdd 5.4.0)

| Id | Commit | Hueco | Cambio | Ficheros | Tests |
|---|---|---|---|---|---|
| U-11.1 | `feat(doc): Mermaid del sitio Markdown referenciado sin copiarlo` | G50 | Opción nueva `imprimir["markdown"]["mermaid_js_ref"]` (`str`, defecto `None`): **ruta relativa a `docs/`** en formato POSIX (sin `..`, sin raíz, sin `\`, sin esquema) o URL `https://`. Se escribe en `extra_javascript` sin copiar nada; con una ruta relativa añade también `theme.font: false` (sitio sin Internet). Excluyente con `mermaid_js` (`DocumentationConfigError` si vienen las dos). El valor va a YAML con `json.dumps`, como `site_name` | `print_config_manager.py`, `documentation_orchestrator.py` (`_check_markdown_files`), `markdown_generator.py` (`_write_machine_files`), `_site.py` (`mkdocs_yml(..., mermaid_src: str \| None)`), `docs/api/database_documentation.md`, `docs/examples/markdown_documentation.md`, `CHANGELOG.md` | `mkdocs.yml` con la ruta y con la URL; nada copiado y nada en `manifest.json` → `files`; las dos opciones → error; `..`, `/abs`, `C:\x`, `javascript:`, `http:` y cadena vacía → error; `zensical build --strict` de la carpeta con el fichero puesto en la ruta; `mermaid_js` sin cambios |
| U-11.2 | `feat(doc): índice de páginas en manifest.json` | G51 | `manifest.json` → `format_version` **2** con `pages`: una entrada por página `.md` escrita, en el orden de la `nav` (portada, secciones, base de datos, trazabilidad, cambios) y dentro de cada sección índice → letras → objetos. Campos: `path` (relativa a `docs/`), `title` (texto plano del H1, **sin** escapes de Markdown), `section` (`home`, `tables`, `views`, `routines`, `database`, `traceability`, `changes`), `role` (`home`, `index`, `letter`, `object`, `page`), `letter` (en `letter`), `id` y `kind` del catálogo (en `object`). Determinista. Se lee igual un `manifest.json` v1 anterior (limpieza de huérfanos: `_writer.py:141` solo mira `format`) | `_writer.py` (`publish(metadata, pages)`, `MANIFEST_FORMAT_VERSION = 2`), `markdown_generator.py` (recoge las entradas en `_emit`, `_write_home`, índices de sección y `traceability`/`changes`), `_site_pages.py` (título de cada índice por letra), docs de la API (contrato del manifiesto), ADR-006 (enmienda: el manifiesto como contrato versionado), `CHANGELOG.md` | Cada `.md` de `files` aparece una sola vez en `pages` y viceversa; `title` = H1 sin `#` ni escapes (`ACM_AGENDA`, con `_`, `|` y `*` en el nombre); `id` coincide con `catalog.json`; dos generaciones iguales → mismo `pages`; generación sobre una carpeta con `manifest.json` v1 limpia los huérfanos; sin `catalog_json` las entradas `object` siguen teniendo `id` |
| release | `release: v5.4.0` | — | MINOR (opción y campo nuevos, compatibles) | `pyproject.toml`, `CHANGELOG.md` | Suite + `zensical build --strict`; wheel y `.sha256` en la release |

Las dos fases son independientes. Se ejecutan en una sesión de util_bbdd (§5.1 del plan de huecos), no desde aquí.

## 4. Fases en la web (W-11 → web 1.13.0)

| Id | Commit | Hueco | Cambio | Rodeo | Tests |
|---|---|---|---|---|---|
| W-11.0 | `chore(backend): util_bbdd 5.4.0` | — | Pin 5.4.0, URL del wheel y lock (hash del `.sha256` de la release). Sin cambios de código | — | Suite completa |
| W-11.1 | `feat(backend): Mermaid de la documentación Markdown fuera de cada ejecución` | G50 | Job: si `UBW_MERMAID_JS` existe, pasa `mermaid_js_ref = "assets/javascripts/mermaid.min.js"` (no `mermaid_js`) y anota en `inputs/templates.json` → `run.json` `markdown_mermaid = {"mode": "referenced", "path": "outputs/markdown/documentacion/docs/assets/javascripts/mermaid.min.js", "sha256": …}`. Sin el fichero, como hoy (aviso; Material carga de unpkg). `zip_stream` admite **entradas extra** `(ruta en el ZIP, fichero del servidor)`; `download_archive` (sin `format` y con `markdown`) añade el Mermaid de `UBW_MERMAID_JS` en esa ruta si la ejecución lo tiene `referenced` y no hay ya un artefacto con esa ruta. Si al descargar el fichero ya no existe, el ZIP sale sin él y con cabecera `X-UBW-Warning` | Se retira la copia (D11-4: las antiguas se quedan) | Job: no hay `mermaid.min.js` en `outputs/`, `mkdocs.yml` lo referencia, `run.json` lo anota; ZIP `markdown` y completo con el fichero (mismo contenido que `UBW_MERMAID_JS`); ejecución antigua (copia registrada) sin duplicado; `UBW_MERMAID_JS` ausente al descargar; tamaño del run ~5,5 MB menor |
| W-11.2 | `feat(backend,frontend): árbol del visor Markdown desde el índice de páginas` | G51 | Backend: `GET /api/v1/runs/{id}/markdown-pages` → `MarkdownPagesOut {source: "manifest" \| "paths", pages: [{path, title, section, role, letter, kind, artifact_id}]}`. Lee `outputs/markdown/documentacion/manifest.json` (artefacto registrado, ≤ 8 MB, `format` y `format_version ≥ 2`), y solo devuelve páginas cuyo `path` es un artefacto `.md` registrado; si no hay índice, `source = "paths"` con la deducción actual (portada en el backend). 404 si la ejecución no es una documentación con Markdown. Frontend: `useMarkdownPages`, `buildPages` acepta el índice; árbol con títulos, búsqueda por título y ruta, secciones `traceability`/`changes` | `markdownNav.buildPages` por rutas **se mantiene** como alternativa para ejecuciones anteriores a 5.4.0 | API: índice v2, manifiesto v1 → `paths`, manifiesto corrupto o enorme → `paths`, `path` no registrado descartado, 404, permisos (no miembro → 404). Frontend: títulos en el árbol, búsqueda por nombre real, alternativa por rutas. El test de contrato T2 pasa a comprobar `pages` contra los ficheros |
| W-11.3 | `docs: G50 y G51 resueltos en util_bbdd 5.4.0` | G50, G51 | GAPS (resueltos), guía `documentacion.md` (Mermaid en el ZIP, árbol con nombres reales), ADR-007 (enmienda: Mermaid fuera del run), ROADMAP | — | `zensical build --strict` |
| release | `release: v1.13.0` | — | MINOR (endpoint nuevo) | — | Comandos de desarrollo + prueba manual |

Orden: W-11.0 → W-11.1 → W-11.2 → W-11.3 → release. W-11.1 y W-11.2 son independientes entre sí.

## 5. Contrato HTTP nuevo (W-11.2)

```text
GET /api/v1/runs/{run_id}/markdown-pages
  200 MarkdownPagesOut
      source: "manifest" | "paths"
      pages: [{ path: str, title: str, section: str, role: "home"|"index"|"letter"|"object"|"page",
                letter: str | null, kind: str | null, artifact_id: int }]
  401 · 404 (no existe, no eres miembro, no es una documentación con Markdown o ya se purgó)
```

`GET /runs/{id}/archive` no cambia de contrato (W-11.1 solo añade un fichero al contenido y, si falta, la cabecera
`X-UBW-Warning`).

## 6. Modelo de datos

Sin migración. `run.json` / `runs.manifest` gana `markdown_mermaid` (W-11.1) en las documentaciones nuevas.

## 7. Riesgos (detalle y mitigaciones en el AUDIT_PLAN)

- El Mermaid del ZIP es el de la imagen al **descargar**, no el de la generación.
- `manifest.json` crece (≈150 bytes por página: unos 200 KB en 1 400 páginas).
- Títulos de la BD en el índice: texto no confiable en la SPA.
- Dos formas de construir el árbol durante la convivencia con ejecuciones antiguas.

## 8. Fuera de alcance

- El Mermaid **incrustado** en el informe HTML de la comparación (5,5 MB por informe, ADR-007 enmienda 2026-10-30):
  otro mecanismo (`mermaid_src` de `HtmlDiffReporter`); candidato a un hueco aparte si se quiere el mismo ahorro.
- Limpieza de copias ya guardadas (D11-4).
- Títulos de cabecera con `id` en el visor (R5 de la sesión anterior).
