import { useMantineColorScheme } from '@mantine/core';
import { useEffect, useRef } from 'react';

import type { ColorScheme, Me } from './useAuth';

/**
 * Aplica el tema de la cuenta (1.21.0). La cuenta manda; `localStorage` es solo la copia del primer fotograma.
 *
 * Regla única: se recuerda el último valor de la cuenta ya aplicado y solo se actúa cuando `me.color_scheme` cambia
 * respecto a él (al cargar, tras el login o tras guardarlo). Así una caché de `me` antigua en otra pestaña no vuelve a
 * imponer su tema, y el cambio optimista (que mueve a la vez caché y tema) no provoca bucles. Al cerrar sesión
 * (`me === null`) se olvida, sin tocar el tema, para que el siguiente usuario siempre reciba el suyo.
 */
export function useColorSchemeSync(me: Me | null | undefined): void {
  const { colorScheme, setColorScheme } = useMantineColorScheme();
  const applied = useRef<ColorScheme | null>(null);

  useEffect(() => {
    if (me === null) {
      applied.current = null;
      return;
    }
    if (me === undefined || me.color_scheme === applied.current) return;
    applied.current = me.color_scheme;
    // Se compara con el tema guardado (puede ser `auto`), no con el resuelto.
    if (me.color_scheme !== colorScheme) setColorScheme(me.color_scheme);
  }, [me, colorScheme, setColorScheme]);
}
