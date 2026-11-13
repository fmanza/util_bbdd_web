// Documento del iframe del visor Markdown (M2, ADR-007 enmendado en la 1.12.0).
//
// El iframe es `sandbox="allow-scripts"` **sin** `allow-same-origin`: origen opaco, sin cookie, sin acceso a la SPA ni a
// la API. Dentro solo se ejecuta el script del puente, que es **constante** y se autoriza por su hash (1.15.0): un
// `srcdoc` hereda la CSP de la SPA (`script-src 'self'`), que bloqueaba el script con nonce y dejaba los enlaces sin
// funcionar fuera de `vite dev` (comprobado en Chromium); la SPA autoriza el mismo hash (`BRIDGE_SHA256`, también en
// `SPA_CSP` de `backend/app/core/middleware.py`). El HTML de `marked` (y los SVG de Mermaid) pasa antes por DOMPurify,
// de modo que un `<script>` o un `on*` llegado de la BD documentada se elimina. El puente intercepta los clics en
// enlaces: las anclas (`#col-…`) se
// resuelven dentro; el resto se manda al padre con `postMessage({type: 'ubw-md-nav', href})`, que valida el origen del
// mensaje (`event.source`) y resuelve el destino entre los artefactos registrados (`resolveLink`).
//
// Copiar (1.17.0): el puente añade un botón a cada bloque de código y copia **dentro del iframe** (API del portapapeles,
// con `allow="clipboard-write"`, y si falla `execCommand('copy')`). Copiar desde la SPA no sirve: tras el clic el foco
// es del iframe y Chromium rechaza la escritura del padre (`NotAllowedError`, comprobado). Los textos del botón llegan
// por `data-ubw-copy*` del `<body>`. Los bloques ```sql vienen ya resaltados (`highlightSqlBlocks`).

import DOMPurify from 'dompurify';

import { MAX_HREF } from './markdownNav';

export const NAV_MESSAGE = 'ubw-md-nav';

const STYLE =
  'body{font-family:system-ui,sans-serif;font-size:14px;line-height:1.5;margin:12px;color:#1a1b1e}' +
  'table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:4px 8px}' +
  'pre,code{background:#f4f4f5;padding:2px 4px;border-radius:4px}a[href]{color:#1c7ed6;cursor:pointer}' +
  '.mermaid-diagram{overflow:auto}' +
  // Bloques de código: barra con «Copiar» encima (no tapa el código) y colores del SQL (contraste AA sobre #f4f4f5).
  'pre{padding:8px 12px;overflow:auto}pre code{padding:0}' +
  '.ubw-code-bar{display:flex;justify-content:flex-end;margin:8px 0 -10px}' +
  '.ubw-copy{font:inherit;font-size:12px;cursor:pointer;' +
  'color:#1a1b1e;background:#fff;border:1px solid #ccc;border-radius:4px;padding:2px 8px}' +
  '.ubw-copy:focus-visible{outline:2px solid #1c7ed6;outline-offset:2px}' +
  '.ubw-sr{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden}' +
  '.hljs-keyword,.hljs-built_in{color:#0b5cad;font-weight:600}.hljs-type{color:#7b2fa8}' +
  '.hljs-string{color:#2b7a0b}.hljs-number,.hljs-literal{color:#a34e00}.hljs-comment{color:#5c5f66;font-style:italic}';

/**
 * HTML sin scripts, manejadores `on*`, marcos, objetos ni formularios; admite SVG (diagramas Mermaid).
 *
 * Mermaid 12 dibuja las etiquetas de los diagramas como HTML dentro de `<foreignObject>`: se admite ese elemento como
 * punto de integración HTML para no perder los nombres de tablas y columnas, y su contenido pasa por las mismas reglas
 * (sin `<script>`, `on*` ni `javascript:`).
 */
export function sanitizeMarkdownHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true, svg: true, svgFilters: true },
    ADD_TAGS: ['foreignObject'],
    HTML_INTEGRATION_POINTS: { foreignobject: true },
    FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'form', 'base', 'meta', 'link'],
    FORBID_ATTR: ['srcset', 'formaction', 'xlink:href', 'ping'],
  });
}

/**
 * Script del puente, **constante** (su hash va en las dos CSP): anclas dentro del iframe y el resto de enlaces al padre.
 * El ancla inicial y el origen de la SPA los lee de `data-ubw-hash` y `data-ubw-parent` del `<body>`, que escribe
 * `buildFrameDocument` (el contenido de la página no puede cambiarlos: no se ejecuta ningún otro script). `2048` es
 * `MAX_HREF`; un test vigila que coincidan y que el hash sea el de `BRIDGE_SHA256`.
 */
export const BRIDGE_SCRIPT = `(function(){
var b=document.body,HASH=b.getAttribute('data-ubw-hash')||'',PARENT=b.getAttribute('data-ubw-parent')||'',MAX=2048;
var COPY=b.getAttribute('data-ubw-copy')||'',DONE=b.getAttribute('data-ubw-copied')||'',FAIL=b.getAttribute('data-ubw-copy-failed')||'';
function go(id){if(!id)return;var el=document.getElementById(id);if(el)el.scrollIntoView();}
function dec(t){try{return decodeURIComponent(t);}catch(e){return t;}}
document.addEventListener('click',function(ev){
var t=ev.target,a=t&&t.closest?t.closest('a[href]'):null;if(!a)return;ev.preventDefault();
var h=a.getAttribute('href')||'';
if(h.charAt(0)==='#'){go(dec(h.slice(1)));return;}
if(h.length>MAX||!PARENT)return;
parent.postMessage({type:'ubw-md-nav',href:h},PARENT);
});
if(COPY){
var live=document.createElement('div');live.className='ubw-sr';live.setAttribute('aria-live','polite');b.appendChild(live);
var say=function(btn,msg){btn.textContent=msg;live.textContent=msg;setTimeout(function(){btn.textContent=COPY;},2000);};
var exec=function(text){var ta=document.createElement('textarea'),ok=false;ta.value=text;ta.setAttribute('readonly','');ta.className='ubw-sr';
b.appendChild(ta);ta.select();try{ok=document.execCommand('copy');}catch(e){ok=false;}ta.remove();return ok;};
var copy=function(btn,text){var c=navigator.clipboard;
if(c&&c.writeText){c.writeText(text).then(function(){say(btn,DONE);},function(){say(btn,exec(text)?DONE:FAIL);});return;}
say(btn,exec(text)?DONE:FAIL);};
Array.prototype.forEach.call(document.querySelectorAll('pre'),function(pre){var code=pre.querySelector('code');if(!code)return;
var bar=document.createElement('div'),btn=document.createElement('button');bar.className='ubw-code-bar';
btn.type='button';btn.className='ubw-copy';btn.textContent=COPY;
btn.addEventListener('click',function(){copy(btn,code.textContent||'');});bar.appendChild(btn);pre.parentNode.insertBefore(bar,pre);});
}
if(HASH)go(HASH);
})();`;

/** `sha256` (base64) de `BRIDGE_SCRIPT`: la fuente `'sha256-…'` de la CSP del iframe y de `SPA_CSP` del backend. */
export const BRIDGE_SHA256 = '4eVjDELX9QTEMNrnnTp49RwdFqMku4vwY8r4Uw8MBOo=';

/** Escapa un valor para un atributo HTML entre comillas dobles. */
function attr(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/** CSP del documento del iframe: solo el script del puente (por su hash), estilos en línea e imágenes `data:`. */
export function frameCsp(): string {
  return (
    `default-src 'none'; script-src 'sha256-${BRIDGE_SHA256}'; img-src data:; style-src 'unsafe-inline'; ` +
    "connect-src 'none'; form-action 'none'; base-uri 'none'"
  );
}

/** Textos del botón «Copiar» de los bloques de código (i18n); sin ellos, el puente no añade botones. */
export interface CopyLabels {
  copy: string;
  copied: string;
  failed: string;
}

/**
 * `srcdoc` del iframe: CSP, estilos, el HTML ya limpio y el script del puente.
 *
 * @param safeHtml - Salida de `sanitizeMarkdownHtml` (nunca HTML sin limpiar).
 * @param hash - Ancla que se abre al cargar (`col-id`), o vacío.
 * @param parentOrigin - Origen de la SPA: el único al que el puente envía mensajes.
 * @param copy - Textos del botón «Copiar»; sin ellos, los bloques de código no llevan botón.
 */
export function buildFrameDocument(
  safeHtml: string,
  hash: string,
  parentOrigin: string,
  copy?: CopyLabels,
): string {
  const labels = copy
    ? ` data-ubw-copy="${attr(copy.copy)}" data-ubw-copied="${attr(copy.copied)}"` +
      ` data-ubw-copy-failed="${attr(copy.failed)}"`
    : '';
  return (
    `<!doctype html><html lang="es"><head><meta charset="utf-8">` +
    `<meta http-equiv="Content-Security-Policy" content="${frameCsp()}">` +
    `<style>${STYLE}</style></head>` +
    `<body data-ubw-hash="${attr(hash)}" data-ubw-parent="${attr(parentOrigin)}"${labels}>${safeHtml}` +
    `<script>${BRIDGE_SCRIPT}</script></body></html>`
  );
}

/** Mensaje del puente válido: `{type: 'ubw-md-nav', href: string}` con `href` acotado (AUDIT_PLAN T5). */
export function navHref(data: unknown): string | null {
  if (typeof data !== 'object' || data === null) return null;
  const { type, href } = data as { type?: unknown; href?: unknown };
  if (type !== NAV_MESSAGE || typeof href !== 'string' || href.length === 0 || href.length > MAX_HREF) {
    return null;
  }
  return href;
}
