import { Input } from '@mantine/core';
import type { ReactNode } from 'react';

/**
 * Botón de un formulario en línea (campos en fila, `align="flex-start"`): reserva el hueco de una etiqueta para que
 * el botón quede a la altura de los campos, tengan o no ayuda debajo. Sustituye a los márgenes fijos (`mt={…}`).
 * Regla de formularios: `.github/instructions/frontend.instructions.md` › UI y accesibilidad.
 */
export function InlineAction({ children }: { children: ReactNode }) {
  return (
    <Input.Wrapper label={' '} labelElement="div" labelProps={{ 'aria-hidden': true }}>
      {/* En bloque: la etiqueta es `inline-block` y un botón suelto se quedaría en su misma línea. */}
      <div>{children}</div>
    </Input.Wrapper>
  );
}
