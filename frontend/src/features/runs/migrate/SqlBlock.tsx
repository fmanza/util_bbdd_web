import { Code, ScrollArea } from '@mantine/core';
import { useEffect, useState } from 'react';

// Colores del resaltado con variables de Mantine (siguen el tema claro/oscuro); solo dentro de `.ubw-sql`.
const STYLE = `
.ubw-sql .hljs-keyword, .ubw-sql .hljs-built_in { color: var(--mantine-color-blue-text); font-weight: 600; }
.ubw-sql .hljs-type { color: var(--mantine-color-grape-text); }
.ubw-sql .hljs-string { color: var(--mantine-color-green-text); }
.ubw-sql .hljs-number, .ubw-sql .hljs-literal { color: var(--mantine-color-orange-text); }
.ubw-sql .hljs-comment { color: var(--mantine-color-dimmed); font-style: italic; }
`;

type Highlighter = (code: string) => string;
let highlighter: Promise<Highlighter> | null = null;

/** `highlight.js` (núcleo + SQL) cargado una vez y bajo demanda. */
function loadHighlighter(): Promise<Highlighter> {
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
 * SQL con resaltado. `highlight.js` escapa el código y solo añade `<span class="hljs-…">`, así que su salida es segura
 * como HTML; hasta que carga se muestra el texto plano.
 */
export function SqlBlock({
  code,
  maxHeight = 360,
  label,
}: {
  code: string;
  maxHeight?: number;
  label?: string;
}) {
  const [html, setHtml] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    void loadHighlighter().then((highlight) => {
      if (alive) setHtml(highlight(code));
    });
    return () => {
      alive = false;
    };
  }, [code]);

  return (
    <ScrollArea.Autosize mah={maxHeight} className="ubw-sql" aria-label={label}>
      <style>{STYLE}</style>
      {html === null ? (
        <Code block>{code}</Code>
      ) : (
        <Code block>
          <span dangerouslySetInnerHTML={{ __html: html }} />
        </Code>
      )}
    </ScrollArea.Autosize>
  );
}
