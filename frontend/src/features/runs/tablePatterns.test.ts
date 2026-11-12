import { describe, expect, it } from 'vitest';

// 260 casos generados con `fnmatch.fnmatchcase(nombre.lower(), patrón.lower())` de Python, la misma comprobación que
// `TableFilter` de util_bbdd: `[patrón, nombre, casa]`.
import cases from './tablePatterns.cases.json';
import { buildFilter, globToRegExp, matches, splitPatterns } from './tablePatterns';

describe('patrones del filtro de tablas', () => {
  it('traduce los patrones igual que fnmatch de Python (util_bbdd)', () => {
    const failures = (cases as [string, string, boolean][]).filter(
      ([pattern, name, expected]) =>
        globToRegExp(pattern.toLowerCase()).test(name.toLowerCase()) !== expected,
    );
    expect(failures).toEqual([]);
  });

  it('separa por comas sin vacíos ni repetidos', () => {
    expect(splitPatterns(' MVG_* ,, COB_*, MVG_* ')).toEqual(['MVG_*', 'COB_*']);
    expect(splitPatterns('')).toEqual([]);
    expect(splitPatterns(undefined)).toEqual([]);
  });

  it('excluir gana a incluir, sin incluir entra todo y no distingue mayúsculas', () => {
    const filter = buildFilter('mvg_*', '*_BAK');
    expect(matches(filter, 'MVG_PEDIDO')).toBe(true);
    expect(matches(filter, 'MVG_PEDIDO_BAK')).toBe(false);
    expect(matches(filter, 'COB_LINEA')).toBe(false);
    const onlyExclude = buildFilter('', 'TMP_*');
    expect(matches(onlyExclude, 'COB_LINEA')).toBe(true);
    expect(matches(onlyExclude, 'tmp_x')).toBe(false);
  });
});
