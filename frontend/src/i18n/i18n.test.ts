import { describe, expect, it } from 'vitest';

import i18n, { initialLanguage, LANGUAGE_STORAGE_KEY, loadFeatureMessages } from '.';
import enCoreRaw from './en/core.json?raw';
import enFeaturesRaw from './en/features.json?raw';
import esCoreRaw from './es/core.json?raw';
import features from './es/features.json';
import esFeaturesRaw from './es/features.json?raw';

/** Claves hoja `a.b.c` → texto (sin pasar por i18next, que fusiona los bundles en los objetos importados). */
function flatten(value: unknown, prefix = '', out = new Map<string, string>()): Map<string, string> {
  if (value !== null && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) flatten(child, prefix ? `${prefix}.${key}` : key, out);
  } else {
    out.set(prefix, String(value));
  }
  return out;
}

const placeholders = (text: string) => [...text.matchAll(/\{\{\s*(\w+)\s*\}\}/g)].map((m) => m[1]).sort();

describe('traducciones', () => {
  it('las pantallas no repiten las claves del núcleo (que va en el bundle inicial)', () => {
    const CORE = Object.keys(JSON.parse(esCoreRaw) as object);
    expect(Object.keys(features).filter((key) => CORE.includes(key))).toEqual([]);
  });

  it('las pantallas se cargan una sola vez y quedan disponibles', async () => {
    const first = loadFeatureMessages();
    expect(loadFeatureMessages()).toBe(first);
    await first;
    expect(i18n.t('dump.apply.submit')).toBe('Volcar ahora');
  });

  it.each([
    ['core', esCoreRaw, enCoreRaw],
    ['features', esFeaturesRaw, enFeaturesRaw],
  ])('%s: el inglés tiene exactamente las claves y los marcadores del español', (_name, esRaw, enRaw) => {
    const es = flatten(JSON.parse(esRaw));
    const en = flatten(JSON.parse(enRaw));
    expect([...en.keys()]).toEqual([...es.keys()]);
    const mismatched = [...es].filter(
      ([key, text]) => placeholders(text).join() !== placeholders(en.get(key) ?? '').join(),
    );
    expect(mismatched.map(([key]) => key)).toEqual([]);
  });

  it('idioma inicial: copia local, después el navegador y si no, español', () => {
    const languages = Object.getOwnPropertyDescriptor(Navigator.prototype, 'languages');
    const setLanguages = (value: string[]) =>
      Object.defineProperty(navigator, 'languages', { configurable: true, get: () => value });
    try {
      setLanguages(['fr-FR', 'en-US']);
      expect(initialLanguage()).toBe('en');
      localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
      expect(initialLanguage()).toBe('es');
      localStorage.removeItem(LANGUAGE_STORAGE_KEY);
      setLanguages(['fr-FR']);
      expect(initialLanguage()).toBe('es');
    } finally {
      // Vuelve el getter de jsdom.
      Reflect.deleteProperty(navigator, 'languages');
      if (languages) Object.defineProperty(Navigator.prototype, 'languages', languages);
    }
  });
});
