import { describe, expect, it } from 'vitest';

import i18n, { loadFeatureMessages } from '.';
import features from './es/features.json';

describe('traducciones', () => {
  it('las pantallas no repiten las claves del núcleo (que va en el bundle inicial)', () => {
    // No se compara con el objeto de core.json: i18next fusiona en él los bundles añadidos.
    const CORE = ['app', 'common', 'roles', 'nav', 'auth', 'home', 'health', 'notFound'];
    expect(Object.keys(features).filter((key) => CORE.includes(key))).toEqual([]);
  });

  it('las pantallas se cargan una sola vez y quedan disponibles', async () => {
    const first = loadFeatureMessages();
    expect(loadFeatureMessages()).toBe(first);
    await first;
    expect(i18n.t('dump.apply.submit')).toBe('Volcar ahora');
  });
});
