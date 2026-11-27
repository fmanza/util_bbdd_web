import { TextInput } from '@mantine/core';
import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '../test/render';

/**
 * Regla de formularios (`frontend.instructions.md` › UI y accesibilidad): la ayuda va debajo del campo (tema) y los
 * botones de un formulario en línea se alinean con `InlineAction`, no con márgenes fijos.
 */

const SOURCES = import.meta.glob<string>(['/src/**/*.tsx', '!/src/**/*.test.tsx', '!/src/test/**'], {
  query: '?raw',
  import: 'default',
  eager: true,
});

describe('regla de alineación de formularios', () => {
  it('el tema pone la ayuda debajo del campo', () => {
    renderWithProviders(<TextInput label="Campo" description="Ayuda" />);

    const input = screen.getByRole('textbox', { name: 'Campo' });
    const help = screen.getByText('Ayuda');
    expect(input.compareDocumentPosition(help) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('ningún formulario cambia el orden ni alinea botones con márgenes fijos', () => {
    const offenders = Object.entries(SOURCES)
      .filter(([, code]) => /inputWrapperOrder=|<Button\b[^>]*\bmt=\{\d+\}/.test(code))
      .map(([path]) => path);
    expect(offenders).toEqual([]);
  });
});
