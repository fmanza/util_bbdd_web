import type { CSSProperties } from 'react';

/**
 * Rejilla que coloca tantas columnas como quepan (de al menos `minRem`) sin pasar de `maxCols`; en un contenedor
 * estrecho, una sola columna sin desbordar. Depende del ancho real del contenedor, no del de la ventana.
 */
export function autoGrid(minRem: number, maxCols: number, gap = 'var(--mantine-spacing-md)'): CSSProperties {
  const share = `calc((100% - ${maxCols - 1} * ${gap}) / ${maxCols})`;
  return {
    display: 'grid',
    gap,
    gridTemplateColumns: `repeat(auto-fill, minmax(min(100%, max(${minRem}rem, ${share})), 1fr))`,
    alignItems: 'start',
  };
}
