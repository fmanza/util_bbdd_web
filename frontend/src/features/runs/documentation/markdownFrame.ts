// Documento del iframe del visor Markdown (M2, ADR-007 enmendado en la 1.12.0).
//
// El iframe es `sandbox="allow-scripts"` **sin** `allow-same-origin`: origen opaco, sin cookie, sin acceso a la SPA ni a
// la API. Dentro solo se ejecuta el script del puente, autorizado por un nonce aleatorio por render en la CSP; el HTML de
// `marked` (y los SVG de Mermaid) pasa antes por DOMPurify, de modo que un `<script>` o un `on*` llegado de la BD
// documentada se elimina y nunca hereda el nonce. El puente intercepta los clics en enlaces: las anclas (`#col-…`) se
// resuelven dentro; el resto se manda al padre con `postMessage({type: 'ubw-md-nav', href})`, que valida el origen del
// mensaje (`event.source`) y resuelve el destino entre los artefactos registrados (`resolveLink`).

import DOMPurify from 'dompurify';

import { MAX_HREF } from './markdownNav';

export const NAV_MESSAGE = 'ubw-md-nav';

const STYLE =
  'body{font-family:system-ui,sans-serif;font-size:14px;line-height:1.5;margin:12px;color:#1a1b1e}' +
  'table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:4px 8px}' +
  'pre,code{background:#f4f4f5;padding:2px 4px;border-radius:4px}a[href]{color:#1c7ed6;cursor:pointer}' +
  '.mermaid-diagram{overflow:auto}';

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

/** Nonce aleatorio (128 bits, hexadecimal) para la CSP de cada render. */
export function newNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

/** JSON seguro dentro de `<script>` (sin `<`, `>` ni `&` literales; U+2028/9 son válidos en JS desde ES2019). */
function scriptJson(value: unknown): string {
  return JSON.stringify(value).replace(/</g, '\\u003c').replace(/>/g, '\\u003e').replace(/&/g, '\\u0026');
}

/** Script del puente: anclas dentro del iframe, el resto de enlaces al padre (solo a `parentOrigin`). */
function bridge(hash: string, parentOrigin: string): string {
  return `(function(){
var HASH=${scriptJson(hash)},PARENT=${scriptJson(parentOrigin)},MAX=${MAX_HREF};
function go(id){if(!id)return;var el=document.getElementById(id);if(el)el.scrollIntoView();}
function dec(t){try{return decodeURIComponent(t);}catch(e){return t;}}
document.addEventListener('click',function(ev){
var t=ev.target,a=t&&t.closest?t.closest('a[href]'):null;if(!a)return;ev.preventDefault();
var h=a.getAttribute('href')||'';
if(h.charAt(0)==='#'){go(dec(h.slice(1)));return;}
if(h.length>MAX)return;
parent.postMessage({type:${scriptJson(NAV_MESSAGE)},href:h},PARENT);
});
if(HASH)go(HASH);
})();`;
}

export function frameCsp(nonce: string): string {
  return (
    `default-src 'none'; script-src 'nonce-${nonce}'; img-src data:; style-src 'unsafe-inline'; ` +
    "connect-src 'none'; form-action 'none'; base-uri 'none'"
  );
}

/**
 * `srcdoc` del iframe: CSP con nonce, estilos, el HTML ya limpio y el script del puente.
 *
 * @param safeHtml - Salida de `sanitizeMarkdownHtml` (nunca HTML sin limpiar).
 * @param hash - Ancla que se abre al cargar (`col-id`), o vacío.
 * @param parentOrigin - Origen de la SPA: el único al que el puente envía mensajes.
 */
export function buildFrameDocument(
  safeHtml: string,
  nonce: string,
  hash: string,
  parentOrigin: string,
): string {
  return (
    `<!doctype html><html lang="es"><head><meta charset="utf-8">` +
    `<meta http-equiv="Content-Security-Policy" content="${frameCsp(nonce)}">` +
    `<style>${STYLE}</style></head><body>${safeHtml}` +
    `<script nonce="${nonce}">${bridge(hash, parentOrigin)}</script></body></html>`
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
