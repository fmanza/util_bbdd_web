import { useEffect, useRef } from 'react';

import { currentLanguage, setLanguage } from '../../i18n';
import type { Language, Me } from './useAuth';

/**
 * Aplica el idioma de la cuenta (`Me.language`), con la misma regla que el tema (`useColorSchemeSync`): solo se actúa
 * cuando el valor de la cuenta cambia respecto al último aplicado (al cargar, tras el login o tras guardarlo), y al
 * cerrar sesión se olvida para que el siguiente usuario reciba el suyo. La copia local solo decide el primer fotograma.
 */
export function useLanguageSync(me: Me | null | undefined): void {
  const applied = useRef<Language | null>(null);

  useEffect(() => {
    if (me === null) {
      applied.current = null;
      return;
    }
    if (me === undefined || me.language === applied.current) return;
    applied.current = me.language;
    if (me.language !== currentLanguage()) void setLanguage(me.language);
  }, [me]);
}
