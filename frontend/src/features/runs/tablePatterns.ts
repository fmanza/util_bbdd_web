// Filtro de tablas de la documentación (util_bbdd 5.5.0) en el navegador, para «Probar patrones» antes de lanzar.
//
// Misma semántica que `TableFilter` de util_bbdd (`fnmatch.fnmatchcase` sobre nombres en minúsculas): `*` cualquier
// texto, `?` un carácter, `[ABC]` uno de esos caracteres y `[!ABC]` cualquiera menos esos; sin distinguir mayúsculas.
// Sin `incluir` entra todo; `excluir` gana a `incluir`.

/** Patrones separados por comas, sin vacíos ni repetidos (como `split_patterns` del backend). */
export function splitPatterns(value: string | undefined | null): string[] {
  return [
    ...new Set(
      (value ?? '')
        .split(',')
        .map((part) => part.trim())
        .filter(Boolean),
    ),
  ];
}

const SPECIAL = /[.*+?^${}()|[\]\\]/g;

/** Patrón *glob* → expresión regular anclada (traducción de `fnmatch.translate`). */
export function globToRegExp(pattern: string): RegExp {
  let out = '';
  let i = 0;
  while (i < pattern.length) {
    const char = pattern.charAt(i);
    i += 1;
    if (char === '*') {
      out += '.*';
    } else if (char === '?') {
      out += '.';
    } else if (char === '[') {
      let j = i;
      if (pattern.charAt(j) === '!') j += 1;
      if (pattern.charAt(j) === ']') j += 1;
      while (j < pattern.length && pattern.charAt(j) !== ']') j += 1;
      if (j >= pattern.length) {
        out += '\\[';
      } else {
        // `\` y `]` literales dentro de la clase (en JS, `[]` sería una clase vacía)
        let body = pattern.slice(i, j).replace(/\\/g, '\\\\').replace(/]/g, '\\]');
        i = j + 1;
        if (body.startsWith('!')) body = `^${body.slice(1)}`;
        else if (body.startsWith('^')) body = `\\${body}`;
        out += `[${body}]`;
      }
    } else {
      out += char.replace(SPECIAL, '\\$&');
    }
  }
  return new RegExp(`^(?:${out})$`, 's');
}

export interface TableFilter {
  include: RegExp[];
  exclude: RegExp[];
}

export function buildFilter(
  include: string | undefined | null,
  exclude: string | undefined | null,
): TableFilter {
  const compile = (value: string | undefined | null) =>
    splitPatterns(value).map((pattern) => globToRegExp(pattern.toLowerCase()));
  return { include: compile(include), exclude: compile(exclude) };
}

/** El objeto se documenta: casa con algún patrón de `incluir` (o no hay) y con ninguno de `excluir`. */
export function matches(filter: TableFilter, name: string): boolean {
  const folded = name.toLowerCase();
  const included = filter.include.length === 0 || filter.include.some((re) => re.test(folded));
  return included && !filter.exclude.some((re) => re.test(folded));
}
