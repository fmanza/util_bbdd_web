import { act, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { Providers } from '../../app/Providers';
import { MarkdownPreview } from './ArtifactBrowser';
import { FRAME_PALETTES } from './documentation/frameTheme';

// Los diagramas se marcan con el tema con el que se dibujaron (Mermaid real no corre en jsdom).
vi.mock('./mermaid', () => ({
  renderMermaidBlocks: (html: string, scheme: 'light' | 'dark' = 'light') =>
    Promise.resolve(`${html}<!--mermaid:${scheme}-->`),
}));

function switchToDark() {
  localStorage.setItem('ubw-color-scheme', 'dark');
  window.dispatchEvent(
    new StorageEvent('storage', { key: 'ubw-color-scheme', newValue: 'dark', storageArea: localStorage }),
  );
}

describe('MarkdownPreview', () => {
  it('al cambiar de tema vuelve a dibujar el documento una sola vez, con estilos y diagramas a la par', async () => {
    render(
      <Providers>
        <MarkdownPreview title="Vista previa" source={'# Hola'} />
      </Providers>,
    );
    const frame = await screen.findByTitle('Vista previa');
    await waitFor(() => expect(frame.getAttribute('srcdoc')).toContain('<!--mermaid:light-->'));
    expect(frame.getAttribute('srcdoc')).toContain(FRAME_PALETTES.light.background);

    const seen: string[] = [];
    const observer = new MutationObserver(() => seen.push(frame.getAttribute('srcdoc') ?? ''));
    observer.observe(frame, { attributes: true, attributeFilter: ['srcdoc'] });
    act(switchToDark);

    await waitFor(() => expect(frame.getAttribute('srcdoc')).toContain('<!--mermaid:dark-->'));
    observer.disconnect();
    expect(frame.getAttribute('srcdoc')).toContain(FRAME_PALETTES.dark.background);
    // Sin un paso intermedio con estilos oscuros y diagramas claros (dos recargas del iframe).
    expect(seen).toHaveLength(1);
  });
});
