// Diagramas Mermaid del Markdown de los artefactos (p. ej. `comparacion.md`): se dibujan aquí, en la SPA, y el SVG
// resultante sustituye al bloque de código antes de pasar al iframe `sandbox=""` sin scripts. Las etiquetas vienen de
// la BD comparada: `securityLevel: 'strict'` las escapa y limpia el SVG con DOMPurify. Mermaid solo se descarga si
// el Markdown trae algún diagrama.

let counter = 0;

// util_bbdd no genera directivas (`%%{init: …}%%`) ni frontmatter (`---`), pero no escapa los saltos de línea de los
// nombres (GAPS G46): un nombre de tabla con `\n` podría colarlos y cambiar la configuración del dibujo (`themeCSS`…).
const DIRECTIVE = /%%\{[\s\S]*?\}%%/g;
const FRONTMATTER = /^\s*---\r?\n[\s\S]*?\r?\n---\s*(\r?\n|$)/;

/** Texto del diagrama sin directivas ni frontmatter: solo cuenta la configuración de `initialize`. */
export function stripMermaidConfig(text: string): string {
  return text.replace(FRONTMATTER, '').replace(DIRECTIVE, '');
}

/** Sustituye en `html` (salida de `marked`) cada `<pre><code class="language-mermaid">` por su SVG. Un diagrama que
 *  Mermaid no sabe dibujar se queda como código. */
export async function renderMermaidBlocks(html: string): Promise<string> {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const blocks = Array.from(doc.querySelectorAll('pre > code.language-mermaid'));
  if (blocks.length === 0) return html;

  const { default: mermaid } = await import('mermaid');
  mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'default' });
  // `render` en serie: Mermaid no admite dibujar varios diagramas a la vez.
  for (const code of blocks) {
    try {
      const { svg } = await mermaid.render(`ubw-mermaid-${++counter}`, stripMermaidConfig(code.textContent));
      const figure = doc.createElement('div');
      figure.className = 'mermaid-diagram';
      figure.innerHTML = svg;
      code.parentElement?.replaceWith(figure);
    } catch (err) {
      console.warn('[mermaid] render error:', err);
    }
  }
  return doc.body.innerHTML;
}
