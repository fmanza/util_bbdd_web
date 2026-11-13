import { describe, expect, it } from 'vitest';

import { sanitizeMarkdownHtml } from './documentation/markdownFrame';
import { highlightSqlBlocks, loadSqlHighlighter } from './sqlHighlight';

// highlightSqlBlocks (visor Markdown) y el cargador compartido con SqlCode/SqlBlock.
describe('resaltado de SQL', () => {
  it('colorea solo los bloques ```sql del HTML de marked', async () => {
    const html =
      '<p>DDL</p><pre><code class="language-sql">CREATE TABLE t (id INTEGER);</code></pre>' +
      '<pre><code class="language-text">CREATE TABLE no</code></pre>';
    const out = await highlightSqlBlocks(html);
    expect(out).toContain('<span class="hljs-keyword">CREATE TABLE</span>');
    expect(out).toContain('<span class="hljs-type">INTEGER</span>');
    expect(out).toContain('<code class="language-text">CREATE TABLE no</code>');
  });

  it('sin bloques SQL devuelve el HTML tal cual', async () => {
    const html = '<p>sin código</p>';
    expect(await highlightSqlBlocks(html)).toBe(html);
  });

  it('un DDL con marcado sale escapado y sin scripts tras la limpieza', async () => {
    const html =
      '<pre><code class="language-sql">CREATE VIEW "&lt;img src=x onerror=alert(1)&gt;" AS SELECT 1;</code></pre>';
    const out = sanitizeMarkdownHtml(await highlightSqlBlocks(html));
    expect(out).toContain('&lt;img src=x onerror=alert(1)&gt;');
    expect(out).not.toMatch(/<img|onerror=alert\(1\)"/);
  });

  it('el resaltador escapa el texto', async () => {
    const highlight = await loadSqlHighlighter();
    expect(highlight("SELECT '<b>' FROM t")).toContain('&lt;b&gt;');
  });
});
