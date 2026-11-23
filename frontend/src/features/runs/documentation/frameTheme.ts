// Colores de los documentos de los iframes de Markdown (visor de documentación y vista previa de artefactos) en los
// dos temas (1.21.0). Los iframes no heredan las variables de Mantine (origen opaco, `srcdoc`): los colores van en su
// propio `<style>`. Todo texto cumple contraste AA (≥ 4.5:1) sobre el fondo y sobre el fondo del código
// (`frameTheme.test.ts`).

export type FrameScheme = 'light' | 'dark';

export interface FramePalette {
  background: string;
  text: string;
  border: string;
  codeBackground: string;
  link: string;
  buttonBackground: string;
  keyword: string;
  type: string;
  string: string;
  number: string;
  comment: string;
}

export const FRAME_PALETTES: Record<FrameScheme, FramePalette> = {
  light: {
    background: '#ffffff',
    text: '#1a1b1e',
    border: '#cccccc',
    codeBackground: '#f4f4f5',
    // Antes #1c7ed6 (4.2:1 sobre blanco, no llegaba a AA).
    link: '#1864ab',
    buttonBackground: '#ffffff',
    keyword: '#0b5cad',
    type: '#7b2fa8',
    string: '#2b7a0b',
    number: '#a34e00',
    comment: '#5c5f66',
  },
  // Fondos de Mantine en oscuro (`dark-7` y `dark-6`) para que el iframe no destaque sobre la página.
  dark: {
    background: '#242424',
    text: '#c9c9c9',
    border: '#4a4a4a',
    codeBackground: '#2e2e2e',
    link: '#74c0fc',
    buttonBackground: '#2e2e2e',
    keyword: '#8ab4f8',
    type: '#d0a3ff',
    string: '#8fd18f',
    number: '#ffb070',
    comment: '#a6a7ab',
  },
};

/** Estilos comunes de un documento Markdown en `scheme`: página, tablas, código y enlaces. */
export function frameBaseStyle(scheme: FrameScheme): string {
  const p = FRAME_PALETTES[scheme];
  return (
    `:root{color-scheme:${scheme}}html{background:${p.background}}` +
    `body{font-family:system-ui,sans-serif;font-size:14px;line-height:1.5;margin:12px;` +
    `color:${p.text};background:${p.background}}` +
    `table{border-collapse:collapse}td,th{border:1px solid ${p.border};padding:4px 8px}` +
    `pre,code{background:${p.codeBackground};padding:2px 4px;border-radius:4px}a[href]{color:${p.link}}`
  );
}
