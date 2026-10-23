import { describe, expect, it } from 'vitest';

import coreRaw from './es/core.json?raw';

// Fuentes de la app como texto (Vite): sirven para seguir los imports sin ejecutarlos.
const SOURCES = import.meta.glob<string>(
  ['/src/**/*.{ts,tsx}', '!/src/**/*.test.{ts,tsx}', '!/src/test/**'],
  {
    query: '?raw',
    import: 'default',
    eager: true,
  },
);

const STATIC_IMPORT = /^\s*import\s[^;]*?from\s+'(\.{1,2}\/[^']+)'/gm;
const KEY_NAMESPACE = /\bt\(\s*['`]([a-zA-Z]+)\./g;

function resolve(from: string, relative: string): string | undefined {
  const parts = from.split('/').slice(0, -1);
  for (const segment of relative.split('/')) {
    if (segment === '..') parts.pop();
    else if (segment !== '.') parts.push(segment);
  }
  const base = parts.join('/');
  return [`${base}.tsx`, `${base}.ts`, `${base}/index.ts`, `${base}/index.tsx`].find(
    (path) => path in SOURCES,
  );
}

/** Módulos que el router importa de forma estática (los `import()` de las rutas lazy no cuentan). */
function eagerModules(entry: string): Set<string> {
  const seen = new Set<string>();
  const pending = [entry];
  while (pending.length > 0) {
    const file = pending.pop() as string;
    if (seen.has(file)) continue;
    seen.add(file);
    for (const match of (SOURCES[file] ?? '').matchAll(STATIC_IMPORT)) {
      const target = resolve(file, match[1] as string);
      if (target) pending.push(target);
    }
  }
  return seen;
}

describe('traducciones del bundle inicial', () => {
  it('lo que se ve sin pasar por una ruta lazy solo usa claves de core.json', () => {
    const core = new Set(Object.keys(JSON.parse(coreRaw) as Record<string, unknown>));
    const modules = eagerModules('/src/app/router.tsx');
    const misses = [...modules].flatMap((file) =>
      [...(SOURCES[file] ?? '').matchAll(KEY_NAMESPACE)]
        .map((match) => match[1] as string)
        .filter((namespace) => !core.has(namespace))
        .map((namespace) => `${file}: ${namespace}`),
    );

    expect(modules.has('/src/app/Layout.tsx')).toBe(true); // el recorrido sigue los imports
    expect(misses).toEqual([]);
  });
});
