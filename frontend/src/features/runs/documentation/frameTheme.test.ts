import { describe, expect, it } from 'vitest';

import { FRAME_PALETTES, frameBaseStyle, type FrameScheme } from './frameTheme';

/** Luminancia relativa (WCAG 2.2) de un color `#rrggbb`. */
function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const v = parseInt(hex.slice(i, i + 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  }) as [number, number, number];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

describe.each<FrameScheme>(['light', 'dark'])('paleta %s', (scheme) => {
  const p = FRAME_PALETTES[scheme];

  it('todo texto cumple AA (4.5:1) sobre el fondo y sobre el fondo del código', () => {
    const texts = {
      text: p.text,
      link: p.link,
      keyword: p.keyword,
      type: p.type,
      string: p.string,
      number: p.number,
      comment: p.comment,
    };
    for (const [name, color] of Object.entries(texts)) {
      for (const background of [p.background, p.codeBackground]) {
        expect(contrast(color, background), `${name} ${color} sobre ${background}`).toBeGreaterThanOrEqual(
          4.5,
        );
      }
    }
    expect(contrast(p.text, p.buttonBackground)).toBeGreaterThanOrEqual(4.5);
  });

  it('el foco del botón «Copiar» (color del enlace) cumple 3:1 sobre el fondo', () => {
    expect(contrast(p.link, p.background)).toBeGreaterThanOrEqual(3);
  });

  it('los estilos declaran el esquema y el fondo del documento', () => {
    const style = frameBaseStyle(scheme);
    expect(style).toContain(`color-scheme:${scheme}`);
    expect(style).toContain(`background:${p.background}`);
    expect(style).toContain(`color:${p.text}`);
  });
});
