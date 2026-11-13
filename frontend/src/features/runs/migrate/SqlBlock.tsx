import { Code, ScrollArea } from '@mantine/core';
import { useEffect, useState } from 'react';

import { loadSqlHighlighter } from '../sqlHighlight';

// Colores del resaltado con variables de Mantine (siguen el tema claro/oscuro); solo dentro de `.ubw-sql`.
const STYLE = `
.ubw-sql .hljs-keyword, .ubw-sql .hljs-built_in { color: var(--mantine-color-blue-text); font-weight: 600; }
.ubw-sql .hljs-type { color: var(--mantine-color-grape-text); }
.ubw-sql .hljs-string { color: var(--mantine-color-green-text); }
.ubw-sql .hljs-number, .ubw-sql .hljs-literal { color: var(--mantine-color-orange-text); }
.ubw-sql .hljs-comment { color: var(--mantine-color-dimmed); font-style: italic; }
`;

/**
 * SQL con resaltado, sin scroll propio (lo pone el contenedor: el explorador usa un área a toda altura). La salida de
 * `highlight.js` es segura como HTML (escapa el código); hasta que carga se muestra el texto plano.
 */
export function SqlCode({ code }: { code: string }) {
  const [html, setHtml] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    void loadSqlHighlighter().then((highlight) => {
      if (alive) setHtml(highlight(code));
    });
    return () => {
      alive = false;
    };
  }, [code]);

  return (
    <div className="ubw-sql">
      <style>{STYLE}</style>
      {html === null ? (
        <Code block>{code}</Code>
      ) : (
        <Code block>
          <span dangerouslySetInnerHTML={{ __html: html }} />
        </Code>
      )}
    </div>
  );
}

/** SQL con resaltado en un área con alto máximo (vista previa de la migración). */
export function SqlBlock({
  code,
  maxHeight = 360,
  label,
}: {
  code: string;
  maxHeight?: number;
  label?: string;
}) {
  return (
    <ScrollArea.Autosize mah={maxHeight} aria-label={label}>
      <SqlCode code={code} />
    </ScrollArea.Autosize>
  );
}
