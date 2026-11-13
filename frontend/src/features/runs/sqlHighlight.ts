// Resaltado de SQL con `highlight.js` (núcleo + SQL), cargado una vez y bajo demanda. Lo usan `SqlCode`/`SqlBlock`
// (migración, explorador) y el visor Markdown (bloques ```sql del DDL de util_bbdd).
//
// `highlight.js` escapa el código y solo añade `<span class="hljs-…">`: su salida es segura como HTML.

export type Highlighter = (code: string) => string;

/** Por encima de este tamaño (caracteres) no se resalta: miles de `<span>` harían lenta la vista previa (hasta 2 MB). */
export const MAX_HIGHLIGHT_CHARS = 200_000;

let highlighter: Promise<Highlighter> | null = null;

/** Función que devuelve el HTML resaltado de un SQL (carga `highlight.js` la primera vez). */
export function loadSqlHighlighter(): Promise<Highlighter> {
  highlighter ??= Promise.all([
    import('highlight.js/lib/core'),
    import('highlight.js/lib/languages/sql'),
  ]).then(([core, sql]) => {
    const hljs = core.default;
    hljs.registerLanguage('sql', sql.default);
    return (code: string) => hljs.highlight(code, { language: 'sql', ignoreIllegals: true }).value;
  });
  return highlighter;
}

/**
 * Resalta los bloques ```sql de un HTML de `marked` (`<pre><code class="language-sql">`). El resto queda igual; sin
 * bloques SQL no carga `highlight.js`. El resultado debe pasar después por `sanitizeMarkdownHtml`.
 */
export async function highlightSqlBlocks(html: string): Promise<string> {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const blocks = Array.from(doc.querySelectorAll('pre > code.language-sql'));
  if (blocks.length === 0) return html;
  const highlight = await loadSqlHighlighter();
  for (const code of blocks) {
    if (code.textContent.length > MAX_HIGHLIGHT_CHARS) continue;
    code.innerHTML = highlight(code.textContent);
    code.classList.add('hljs');
  }
  return doc.body.innerHTML;
}
