# ADR-007 — Sitio HTML de la documentación: origen opaco y URL firmada

- **Estado**: Aceptado
- **Fecha**: 2026-10-22

## Contexto

`DatabaseDocumentation` de util_bbdd genera un sitio HTML de varias páginas (`index.html`, `tables/`, `views/`,
`graphs/*.svg`, `assets/`) que necesita JavaScript para la navegación y el resaltado SQL (un script en línea más
`assets/sql-highlight.js`). Las plantillas escapan los datos (Jinja2 con autoescape), pero los nombres y comentarios
de los objetos vienen de la BD documentada y no son de confianza.

Las vistas previas de la Fase 3 (`iframe sandbox=""` y CSP `sandbox` sin scripts) dejan el sitio sin navegación.
Además, un documento con origen opaco hace las peticiones de sus subrecursos como de otro sitio: la cookie de sesión
(`SameSite=Lax`) no viaja con ellas y el CSS, el JS y los enlaces internos darían 401.

## Decisión

1. **Origen opaco con scripts**: el sitio se sirve con la CSP
   `sandbox allow-scripts allow-popups allow-downloads; default-src 'none'; script-src 'self' 'unsafe-inline';
   style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'none';
   frame-src 'self'; form-action 'none'; base-uri 'none'` (más `frame-ancestors 'self'` solo en el índice raíz,
   ver la enmienda), y en la SPA dentro de un
   `iframe sandbox="allow-scripts allow-popups allow-downloads"`, **nunca** con `allow-same-origin`. Los scripts se
   ejecutan, pero no pueden leer la cookie, el DOM de la SPA ni llamar a la API (`connect-src 'none'`).
2. **URL de capacidad**: `GET /api/v1/runs/{id}/site/{token}/{ruta}`. El token es
   `<user_id>.<caducidad>.<HMAC-SHA256(UBW_APP_SECRET_KEY, "site:{run}:{user}:{caducidad}")>`, caduca a los
   `UBW_SESSION_IDLE_MINUTES` y lo emite `GET /runs/{id}` (`site_url`). En cada petición se comprueba la firma, que el
   usuario sigue activo y que es miembro del proyecto.
3. Solo se sirven **artefactos registrados** del run de tipo `html` (comparación exacta con `artifacts.path`, más
   `safe_path`): ni `run.json`, ni el log, ni rutas con `..`.
4. `Referrer-Policy: no-referrer` para que el token no salga en el `Referer` de los enlaces externos;
   `X-Content-Type-Options: nosniff`.
5. «Abrir en pestaña nueva» usa la misma URL: la CSP `sandbox` mantiene el origen opaco también como documento
   principal.

## Consecuencias

- Quien obtenga la URL puede leer ese sitio mientras no caduque y su usuario siga teniendo acceso; no da acceso a
  nada más. Cerrar la sesión no invalida las URL ya emitidas (caducan solas).
- Fase 6: el informe HTML de comparación de util_bbdd carga Mermaid de un CDN; la CSP lo bloquea (no se admiten
  orígenes externos). Hasta la 1.1.0 la web sustituía esa etiqueta por un `mermaid` vacío local para que el resto del
  script funcionara; desde la 1.2.0 (util_bbdd 4.2.0, GAPS G25) el informe se genera con `mermaid_src=None`: sin
  scripts externos, y su script funciona sin Mermaid (diagramas como texto).
- El Markdown de los artefactos se convierte con `marked` y se muestra en un `iframe srcdoc` con `sandbox=""` y una
  CSP `default-src 'none'`, sin scripts.

## Enmienda 2026-10-24: iframe de detalle del índice

El `index.html` de util_bbdd muestra el detalle de cada objeto en un iframe propio (`detailFrame`). La CSP original lo
bloqueaba en el iframe de la SPA y en «Abrir en pestaña nueva»: sin `frame-src` se aplicaba `default-src 'none'`, y
el `frame-ancestors 'self'` de las páginas de detalle no admite a su padre, el índice, cuyo origen es opaco (ningún
valor de `frame-ancestors`, ni `*`, admite un ancestro opaco).

- Toda página del sitio lleva `frame-src 'self'`: solo puede enmarcar ficheros del propio sitio, que siguen pasando
  por la URL firmada y la lista de artefactos registrados, y que heredan el `sandbox`.
- `frame-ancestors 'self'` solo en el índice raíz (`<carpeta>/index.html`, el de `site_url`). El resto de páginas no
  lo llevan: una web ajena podría enmarcarlas si conoce la URL. Riesgo aceptado: la URL caduca, el contenido es de
  solo lectura y sin formularios (`form-action 'none'`) y no sale en el `Referer` (`no-referrer`).
- La E2E navega al detalle desde el índice y falla ante cualquier bloqueo de iframes (`Framing …`) del sitio.

## Enmienda 2026-10-25: pestañas que abre el sitio

Los enlaces `target="_blank"` del sitio (tarjetas de resumen y enlaces de detalle de las colecciones) abren pestañas
que heredan su `sandbox`, y el navegador bloquea una ventana con `sandbox` cuya respuesta trae un
`Cross-Origin-Opener-Policy` distinto de `unsafe-none` (`ERR_BLOCKED_BY_RESPONSE`). El middleware ponía
`same-origin` en todas las respuestas.

- Las respuestas del sitio llevan `Cross-Origin-Opener-Policy: unsafe-none` (la ruta la pone y el middleware la
  respeta). La SPA, la API y las vistas previas siguen con `same-origin`.
- No se usa `allow-popups-to-escape-sandbox`: las pestañas tendrían el origen real, con la cookie y la API.
- Las páginas del sitio ya tienen origen opaco y sus enlaces llevan `rel="noopener"`; el COOP no les añadía
  aislamiento útil.

## Enmienda 2026-10-30: Mermaid incrustado en el informe de comparación

El informe HTML de comparación y la vista previa de su Markdown mostraban el diagrama de diferencias como texto (G25).

- La imagen trae `mermaid@12.2.0` del `package-lock.json` del frontend (`/app/vendor/mermaid.min.js`,
  `UBW_MERMAID_JS`) y el job lo pasa a util_bbdd como `mermaid_src=Path`: util_bbdd lo **incrusta** en el
  `index.html`. La CSP del sitio no cambia (el script en línea ya se admitía); sigue sin orígenes externos ni
  `connect-src`. Sin el ajuste, o si el fichero falta, el informe se genera con `mermaid_src=None`, como antes.
- Coste: unos 5,5 MB más por informe HTML (cuenta en la cuota del usuario). A cambio el informe descargado se ve
  completo sin red. Se descartan un fichero aparte por ejecución (mismo peso y un artefacto `.js` servible más) y uno
  común de la aplicación (ruta pública nueva; el informe descargado perdería el diagrama).
- Markdown: los bloques `mermaid` se dibujan en la SPA (`renderMermaidBlocks`, Mermaid cargado bajo demanda,
  `securityLevel: 'strict'`) y el SVG pasa al `iframe srcdoc` con `sandbox=""` y la misma CSP sin scripts. Las
  etiquetas vienen de la BD comparada: `strict` las escapa y limpia el SVG con DOMPurify, y la CSP de la SPA no
  admite scripts en línea.
- La E2E de la comparación comprueba el `<svg>` en el informe (origen opaco) y en la vista previa del Markdown.

## Enmienda 2026-11-06: visor de la documentación Markdown con puente de navegación

La vista previa Markdown (`iframe srcdoc` con `sandbox=""`, sin scripts) no puede seguir los enlaces relativos que
genera util_bbdd (`pedidos.md`, `../views/v.md#col-id`): se resuelven contra `about:srcdoc`. El visor de la 1.12.0
(sesión `2026-11-06-doc-output-cards`, alternativa M2) los sigue sin exponer la SPA:

- El iframe pasa a `sandbox="allow-scripts"` **sin** `allow-same-origin`: origen opaco (sin cookie, sin API, sin
  acceso al DOM del padre).
- CSP en el `srcdoc`: `default-src 'none'; script-src 'nonce-<aleatorio por render>'; img-src data:;
  style-src 'unsafe-inline'; connect-src 'none'; form-action 'none'; base-uri 'none'`. Solo se ejecuta el script del
  puente; un `<script>` o un `on*` que se colara no tiene el nonce y el navegador lo bloquea (comprobado en Chromium).
- El HTML de `marked`, con los SVG de Mermaid ya dibujados en la SPA (`securityLevel: 'strict'`), pasa por
  **DOMPurify** antes de añadir el script: sin `script`, `iframe`, `object`, `embed`, `form`, `base`, `meta`, `link`,
  `on*` ni `javascript:`. `foreignObject` se admite como punto de integración HTML porque Mermaid 12 dibuja ahí las
  etiquetas de los diagramas; su contenido pasa por las mismas reglas. DOMPurify pasa a dependencia directa del
  frontend (la versión que ya instalaba Mermaid; el árbol de dependencias no cambia).
- El puente resuelve dentro las anclas (`#col-…`) y manda el resto de clics al padre con
  `postMessage({type: 'ubw-md-nav', href}, <origen de la SPA>)`. El padre acepta solo mensajes cuyo `event.source` es
  la ventana de ese iframe (`event.origin` es `"null"`), con ese formato y `href` de 2048 caracteres como mucho, y
  resuelve el destino **solo entre los artefactos registrados** de `docs/` (sin salir de la carpeta): nunca construye
  una URL de la API con el texto del enlace. Externos: solo `http:`/`https:`, con confirmación y
  `noopener,noreferrer`.
- Sin cambios en `SITE_CSP`, en la URL firmada del sitio HTML ni en las vistas previas de los demás artefactos
  (`sandbox=""`).

## Enmienda 2026-11-06 (1.13.0): Mermaid de la documentación Markdown fuera de cada ejecución

Con util_bbdd 5.4.0 (G50) el job pasa `mermaid_js_ref` en lugar de copiar `UBW_MERMAID_JS` en cada ejecución: el
`mkdocs.yml` referencia `assets/javascripts/mermaid.min.js` y el fichero no se guarda (unos 5,5 MB menos por
ejecución en la cuota).

- El ZIP completo y el Markdown añaden al descargar el `mermaid.min.js` del servidor en esa ruta (`zip_stream` con
  entradas extra), si `run.json` dice `markdown_mermaid.mode = "referenced"` y la ejecución no tiene ya su copia (las
  anteriores la conservan, D11-4). La ruta dentro del ZIP es una constante y el fichero sale de la configuración,
  nunca de la petición ni de `run.json`; el `sha256` que guarda `run.json` es informativo.
- Si el fichero ya no está en el servidor, el ZIP sale sin él con la cabecera `X-UBW-Warning`; el tema del sitio
  publicado carga entonces Mermaid 11 de unpkg (verificado en util_bbdd 5.4.0).
- El visor de la SPA no cambia: dibuja con el Mermaid de la SPA y nunca usa el del run. Tampoco cambia el informe
  HTML de la comparación, que sigue incrustando su Mermaid (enmienda 2026-10-30).

## Alternativas descartadas

- **`allow-same-origin` + scripts**: el sitio podría leer la cookie CSRF y llamar a la API como el usuario.
- **Sin scripts** (como las vistas previas): el sitio pierde la navegación por pestañas y el resaltado.
- **Cookie `SameSite=None`**: abre CSRF en toda la API para resolver un problema de una sola ruta.
- **Subdominio dedicado**: exige DNS y TLS adicionales en un despliegue autoalojado.
