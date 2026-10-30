import { beforeEach, describe, expect, it, vi } from 'vitest';

import { renderMermaidBlocks, stripMermaidConfig } from './mermaid';

// jsdom no puede dibujar (sin layout ni `getBBox`): Mermaid se sustituye y se comprueba qué recibe.
const mermaid = vi.hoisted(() => ({ initialize: vi.fn(), render: vi.fn() }));
vi.mock('mermaid', () => ({ default: mermaid }));

describe('renderMermaidBlocks', () => {
  beforeEach(() => {
    mermaid.initialize.mockReset();
    mermaid.render.mockReset();
  });

  it('sustituye cada bloque mermaid por su SVG, en modo strict', async () => {
    mermaid.render.mockResolvedValue({ svg: '<svg id="d"><g></g></svg>' });
    const html =
      '<h2>Diagrama</h2><pre><code class="language-mermaid">graph LR\n  A["a &amp; b"]</code></pre>' +
      '<pre><code class="language-sql">SELECT 1</code></pre>';

    const out = await renderMermaidBlocks(html);

    expect(mermaid.initialize).toHaveBeenCalledWith(
      expect.objectContaining({ startOnLoad: false, securityLevel: 'strict' }),
    );
    expect(mermaid.render).toHaveBeenCalledWith(expect.any(String), 'graph LR\n  A["a & b"]');
    expect(out).toContain('<div class="mermaid-diagram"><svg id="d">');
    expect(out).not.toContain('language-mermaid');
    expect(out).toContain('<code class="language-sql">SELECT 1</code>');
  });

  it('sin bloques mermaid devuelve el HTML tal cual y no carga Mermaid', async () => {
    const html = '<h1>Hola</h1><pre><code>graph LR</code></pre>';

    expect(await renderMermaidBlocks(html)).toBe(html);
    expect(mermaid.initialize).not.toHaveBeenCalled();
  });

  it('quita las directivas y el frontmatter que un nombre de tabla con saltos de línea podría colar', async () => {
    mermaid.render.mockResolvedValue({ svg: '<svg></svg>' });
    const injected =
      '---\nconfig:\n  themeCSS: "x"\n---\ngraph LR\n  A["t\n%%{init: {"themeCSS": "*{display:none}"}}%%\n"]';

    await renderMermaidBlocks(
      `<pre><code class="language-mermaid">${injected.replace(/"/g, '&quot;')}</code></pre>`,
    );

    const rendered = String(mermaid.render.mock.calls[0]?.[1]);
    expect(rendered).not.toContain('%%{');
    expect(rendered).not.toContain('themeCSS');
    expect(rendered.startsWith('graph LR')).toBe(true);
  });

  it('stripMermaidConfig no toca un diagrama normal', () => {
    const text = 'graph LR\n  A["clientes"] --> B["pedidos"]\n  %% comentario';
    expect(stripMermaidConfig(text)).toBe(text);
  });

  it('un diagrama que Mermaid no sabe dibujar se queda como código', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    mermaid.render.mockRejectedValue(new Error('Parse error'));

    const out = await renderMermaidBlocks('<pre><code class="language-mermaid">graph ??</code></pre>');

    expect(out).toContain('<code class="language-mermaid">graph ??</code>');
  });
});
