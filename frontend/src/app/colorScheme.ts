// Tema de la interfaz (1.21.0): claro, oscuro o el del sistema, guardado en la cuenta (`Me.color_scheme`).
//
// La cuenta manda; `localStorage` solo es la copia con la que `public/color-scheme.js` pinta el primer fotograma antes
// de que arranque React (sin destello). La clave es propia para no depender de la interna de Mantine, y el script la
// repite: `color-scheme.test.ts` vigila que coincidan.

import {
  localStorageColorSchemeManager,
  type MantineColorScheme,
  useComputedColorScheme,
} from '@mantine/core';

export const COLOR_SCHEME_STORAGE_KEY = 'ubw-color-scheme';

export const colorSchemeManager = localStorageColorSchemeManager({ key: COLOR_SCHEME_STORAGE_KEY });

export const COLOR_SCHEMES: readonly MantineColorScheme[] = ['light', 'dark', 'auto'];

/** Tema efectivo (`auto` resuelto con el del sistema), ya en el primer render: lo usan las vistas previas. */
export function useResolvedColorScheme(): 'light' | 'dark' {
  return useComputedColorScheme('light', { getInitialValueInEffect: false });
}
