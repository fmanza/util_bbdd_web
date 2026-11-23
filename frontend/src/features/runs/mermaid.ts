// Diagramas Mermaid del Markdown de los artefactos (p. ej. `comparacion.md`): se dibujan aquí, en la SPA, y el SVG
// resultante sustituye al bloque de código antes de pasar al iframe `sandbox=""` sin scripts. Las etiquetas vienen de
// la BD comparada: `securityLevel: 'strict'` las escapa y limpia el SVG con DOMPurify. Mermaid solo se descarga si
// el Markdown trae algún diagrama.

let counter = 0;

// util_bbdd no genera directivas (`%%{init: …}%%`) ni frontmatter (`---`). Hasta la 5.2.0 no escapaba los saltos de
// línea de los nombres (GAPS G46) y un nombre de tabla con `\n` podía colarlos y cambiar la configuración del dibujo
// (`themeCSS`…); se sigue quitando como defensa (D10-2), para los artefactos generados con versiones anteriores.
const DIRECTIVE = /%%\{[\s\S]*?\}%%/g;
const FRONTMATTER = /^\s*---\r?\n[\s\S]*?\r?\n---\s*(\r?\n|$)/;

/** Texto del diagrama sin directivas ni frontmatter: solo cuenta la configuración de `initialize`. */
export function stripMermaidConfig(text: string): string {
  return text.replace(FRONTMATTER, '').replace(DIRECTIVE, '');
}

// `mermaid.initialize` es global: dos vistas previas a la vez (o un cambio de tema a mitad de un dibujo) mezclarían
// temas. Cada llamada espera a la anterior (1.21.0); un fallo no corta la cola.
let queue: Promise<unknown> = Promise.resolve();

/** Sustituye en `html` (salida de `marked`) cada `<pre><code class="language-mermaid">` por su SVG, con el tema de
 *  `scheme`. Un diagrama que Mermaid no sabe dibujar se queda como código. */
export function renderMermaidBlocks(html: string, scheme: 'light' | 'dark' = 'light'): Promise<string> {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const blocks = Array.from(doc.querySelectorAll('pre > code.language-mermaid'));
  if (blocks.length === 0) return Promise.resolve(html);
  const run = queue.then(() => renderBlocks(doc, blocks, scheme));
  queue = run.catch(() => undefined);
  return run;
}

async function renderBlocks(doc: Document, blocks: Element[], scheme: 'light' | 'dark'): Promise<string> {
  const { default: mermaid } = await import('mermaid');
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'strict',
    theme: scheme === 'dark' ? 'dark' : 'default',
  });
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
