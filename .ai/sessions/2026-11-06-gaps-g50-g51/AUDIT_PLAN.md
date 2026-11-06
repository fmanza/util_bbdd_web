# AUDIT_PLAN — Ola 11: G50 y G51

Revisión del [PLAN](PLAN.md) antes de implementar. Decisiones D11-1 a D11-4 tomadas por el usuario antes del PLAN
([00_REQUEST.md](00_REQUEST.md)); D11-5 a D11-8, aprobadas después («Todo»).

## Funcional

- **F1** (G50) El sitio publicado desde el ZIP debe dibujar los diagramas sin Internet, como hoy. Se cumple si el ZIP
  lleva el fichero en `docs/assets/javascripts/mermaid.min.js` y `mkdocs.yml` lo referencia con la misma ruta.
  *Condición*: test de W-11.1 que abre el ZIP, comprueba el fichero y la línea de `extra_javascript`, y prueba manual
  con `zensical build` del ZIP descomprimido.
- **F2** (G50) Las ejecuciones anteriores llevan su copia registrada: el ZIP no debe añadir una segunda entrada con la
  misma ruta (un ZIP con nombres duplicados confunde a los descompresores). *Condición* (test).
- **F3** (G50) La tarjeta Markdown y la guía dicen hoy «el ZIP incluye Mermaid»: sigue siendo cierto. Los «Ficheros
  auxiliares» ya excluyen `assets/`; en ejecuciones nuevas no habrá artefacto `mermaid.min.js` (el recuento de
  ficheros y el tamaño bajan ~5,5 MB). Sin cambio de textos salvo la guía (W-11.3).
- **F4** (G51) El árbol con títulos debe seguir funcionando con ejecuciones de 5.3.0 (sin `pages`): `source = "paths"`
  con la deducción actual. *Condición*: tests de las dos fuentes.
- **F5** (G51) Búsqueda: por título **y** por ruta (quien conoce el *slug* lo sigue encontrando).
- **F6** (G51) Las secciones nuevas que trae el índice (`traceability`, `changes`) salen en el árbol con su nombre; hoy
  van en «Portada».

## Técnico

- **T1** (G50) El Mermaid del ZIP es el de `UBW_MERMAID_JS` **al descargar**. Si la imagen cambia de versión entre
  la generación y la descarga, el ZIP lleva la nueva. Aceptable (Mermaid 12.x es compatible hacia atrás para
  `erDiagram`); `run.json` guarda el `sha256` del de la generación para saber si difiere. **D11-5** decide si se avisa.
- **T2** (G50) `zip_stream` gana entradas extra fuera del workspace: la ruta del servidor sale de la configuración
  (`settings.mermaid_js`), **nunca** de la petición ni de `run.json`; la ruta dentro del ZIP es una constante. El
  `sha256` de `run.json` es solo informativo.
- **T3** (G50) **PENDIENTE DE VERIFICAR**: qué hace `zensical build --strict` (y `mkdocs build --strict`) si
  `extra_javascript` apunta a un fichero que no está en `docs/`. Una prueba rápida en esta sesión no fue concluyente
  (la build terminó sin errores pero no generó páginas con la carpeta mínima). U-11.1 debe probarlo con una carpeta
  real: es lo que verá un usuario de util_bbdd que use `mermaid_js_ref` sin poner el fichero.
- **T4** (G50) Material for MkDocs: con `extra_javascript` local ausente, ¿vuelve a cargar Mermaid de unpkg? Afecta
  solo al caso «ZIP sin el fichero» (`UBW_MERMAID_JS` borrado al descargar). **PENDIENTE DE VERIFICAR** en U-11.1;
  para la web basta con la cabecera `X-UBW-Warning` y la nota de la guía.
- **T5** (G51) `title` en **texto plano**: util_bbdd escribe el H1 con escapes de Markdown (`md_text`); el índice debe
  guardar el texto sin escapar o la web mostraría `ACM\_AGENDA`. *Condición* en U-11.2 (test con `_`, `|`, `*`).
- **T6** (G51) Tamaño: `manifest.json` ya pesa 88 KB en 630 tablas (hashes de 3 777 ficheros); `pages` añade unos
  200 KB en 1 400 páginas. La web lo lee entero en el backend: límite de 8 MB y respuesta propia (no en
  `RunDetailOut`, que ya ronda 1 MB). `staleTime: Infinity` en el cliente (la ejecución está cerrada).
- **T7** (G51) Validación en el backend: Pydantic con `extra="ignore"` (campos nuevos de futuras versiones no
  rompen), `format == "util_bbdd.doc.markdown"`, `format_version >= 2`; cada `path` se busca entre los artefactos
  `.md` registrados (los que no, se descartan). Cualquier fallo → `source = "paths"`, sin 500.
- **T8** (G51) El test de contrato T2 de la sesión anterior protegía la deducción por carpetas con ejecuciones
  **nuevas**. Con 5.4.0 las nuevas tienen `pages`: el test pasa a comprobar `pages` ↔ ficheros, y la deducción por
  rutas (solo para ejecuciones 5.3.0, cuya estructura ya no cambia) se cubre con tests unitarios de `markdownNav`.
- **T9** Compatibilidad del manifiesto: `format_version` 2 es aditivo. Quien lea con la web 1.12.0 un manifiesto v2
  no se ve afectado (hoy la web no lee `manifest.json`).
- **T10** `exclude-newer`: util_bbdd llega por URL del wheel de la release; si `uv lock` lo exige, excepción
  justificada como en olas anteriores.

## Seguridad

- **S1** `mermaid_js_ref` (util_bbdd): se escribe en YAML con `json.dumps` (sin inyección); solo ruta relativa sin
  `..` ni raíz, o `https://`. Rechazar `http:`, `javascript:`, `data:` y rutas absolutas o de Windows.
- **S2** Entrada extra del ZIP (web): fichero de configuración del servidor, sin rutas del usuario; se comprueba que
  es un fichero regular antes de añadirlo. Mismo control de acceso que hoy (`get_access`).
- **S3** Títulos del índice: vienen de nombres y comentarios de la BD documentada. En la SPA se pintan como texto
  (React escapa); nunca como HTML ni en atributos `href`. La navegación usa `artifact_id`/`path` validados en el
  backend, nunca el título.
- **S4** `GET /markdown-pages`: mismo `get_access` (miembro del proyecto; 404 si no lo es, sin revelar existencia).
  Sin rutas del servidor en errores.

## Simplificaciones

- Sin endpoint para el Mermaid: el visor no lo necesita (dibuja con el de la SPA); solo el ZIP.
- Sin `nav.json` en `docs/` (D11-2): un fichero menos en el sitio publicado.
- Sin limpieza de copias antiguas (D11-4).

## Decisiones (aprobadas por el usuario el 2026-11-06: «Todo»)

| # | Decisión | Aprobado |
|---|---|---|
| D11-5 | ¿Avisar si el Mermaid del ZIP difiere del de la generación (T1)? | **No**: solo se guarda el `sha256` en `run.json`; Mermaid 12.x es compatible |
| D11-6 | Versión de util_bbdd | **5.4.0 (MINOR)**: opción y campo nuevos, compatibles |
| D11-7 | Versión de la web | **1.14.0 (MINOR)**: endpoint nuevo. Enmendada el 2026-11-06 (antes 1.13.0): la 1.13.0 es la de la sesión `2026-11-06-explorer-runs-lists` (D6) |
| D11-8 | Rodeos | La deducción del árbol por rutas **se mantiene** para ejecuciones 5.3.0; la copia de Mermaid **se retira** |

## Veredicto

**GO_CONDICIONAL** — condiciones:

1. ~~Aprobar D11-5 a D11-8~~ — hecho (2026-11-06).
2. U-11.1 resuelve T3 y T4 (comportamiento con el fichero ausente) y lo documenta en la API de util_bbdd.
3. U-11.2 cumple T5 (títulos sin escapes) con test.
4. Las fases `U-11.x` se ejecutan en una sesión de util_bbdd (desde la web no se modifica util_bbdd); la web empieza
   W-11 solo con la release 5.4.0 publicada (wheel y `.sha256`).
5. Tests de F1, F2, F4 y T7 en W-11.1/W-11.2.
