import { afterEach, describe, expect, it, vi } from 'vitest';

import script from '../../public/color-scheme.js?raw';
import { COLOR_SCHEME_STORAGE_KEY } from './colorScheme';

/** Ejecuta `public/color-scheme.js` con el sistema en oscuro o en claro. */
function runScript(systemDark: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((query: string) => ({ matches: systemDark && query.includes('dark'), media: query })),
  );
  // Es el propio script del proyecto (servido desde 'self'); se ejecuta como lo haría el navegador.
  new Function(script)();
  return document.documentElement.getAttribute('data-mantine-color-scheme');
}

describe('public/color-scheme.js', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('usa la misma clave de localStorage que el gestor de Mantine', () => {
    expect(script).toContain(`var KEY = '${COLOR_SCHEME_STORAGE_KEY}';`);
  });

  it('aplica la copia local del tema', () => {
    localStorage.setItem(COLOR_SCHEME_STORAGE_KEY, 'dark');
    expect(runScript(false)).toBe('dark');
    localStorage.setItem(COLOR_SCHEME_STORAGE_KEY, 'light');
    expect(runScript(true)).toBe('light');
  });

  it('sin copia, o con un valor no válido, resuelve el del sistema', () => {
    expect(runScript(true)).toBe('dark');
    localStorage.setItem(COLOR_SCHEME_STORAGE_KEY, 'sepia');
    expect(runScript(false)).toBe('light');
    localStorage.setItem(COLOR_SCHEME_STORAGE_KEY, 'auto');
    expect(runScript(true)).toBe('dark');
  });

  it('con localStorage inaccesible no falla', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('denegado', 'SecurityError');
    });
    expect(runScript(true)).toBe('dark');
  });
});
