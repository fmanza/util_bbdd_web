import { describe, expect, it } from 'vitest';

import { DOCUMENTATION } from '../../test/fixtures_runs';
import { buildParamsView, sameValue } from './runParamsView';
import type { Operation, OperationParam } from './useRuns';

const names = (view: ReturnType<typeof buildParamsView>) =>
  Object.fromEntries(view.cards.map((c) => [c.id, [...c.flags, ...c.fields].map((e) => e.param.name)]));

describe('sameValue', () => {
  it('trata null, undefined y vacío como «sin valor» y compara números con su texto', () => {
    expect(sameValue(null, '')).toBe(true);
    expect(sameValue(undefined, null)).toBe(true);
    expect(sameValue('3', 3)).toBe(true);
    expect(sameValue(false, null)).toBe(false);
    expect(sameValue(['a'], ['a'])).toBe(true);
  });
});

describe('buildParamsView', () => {
  const params = {
    connection: 'origen',
    schema: null,
    word: true,
    html: false,
    table_include: 'cli_*',
    graph_direction: 'both',
    legacy_flag: true,
  };

  it('agrupa como el formulario y separa interruptores de valores', () => {
    const view = buildParamsView('documentation', DOCUMENTATION, params);
    expect(names(view)).toEqual({
      source: ['connection', 'schema'],
      formats: ['word', 'html'],
      filter: ['table_include'],
      graphs: ['graph_direction'],
      saved: ['legacy_flag'],
    });
    const formats = view.cards.find((c) => c.id === 'formats');
    expect(formats?.flags.map((e) => e.param.name)).toEqual(['word', 'html']);
    expect(formats?.fields).toEqual([]);
  });

  it('cuenta y filtra los distintos del valor por defecto (las claves desconocidas cuentan como distintas)', () => {
    const view = buildParamsView('documentation', DOCUMENTATION, params, true);
    expect(view.total).toBe(7);
    // connection (null → origen), html (true → false), table_include y legacy_flag.
    expect(view.changed).toBe(4);
    expect(names(view)).toEqual({
      source: ['connection'],
      formats: ['html'],
      filter: ['table_include'],
      saved: ['legacy_flag'],
    });
  });

  it('marca como inactivos los dependientes de un interruptor apagado', () => {
    const view = buildParamsView('documentation', DOCUMENTATION, { ...params, graphs: false });
    const direction = view.cards.flatMap((c) => c.fields).find((e) => e.param.name === 'graph_direction');
    expect(direction?.inactive).toBe(true);
  });

  it('oculta los parámetros con `requires` apagado y los de otro modo del volcado', () => {
    const base: OperationParam = {
      name: '',
      type: 'string',
      required: false,
      default: null,
      description: '',
      minimum: null,
      maximum: null,
    };
    const op: Operation = {
      name: 'dump_preview',
      form: true,
      title: 'Volcado',
      description: '',
      params: [
        ...DOCUMENTATION.params.filter((p) => ['table_include', 'table_exclude'].includes(p.name)),
        { ...base, name: 'tables' },
        { ...base, name: 'extra', type: 'boolean', default: false },
        { ...base, name: 'extra_detail', requires: 'extra' },
      ],
    };
    const view = buildParamsView('dump_preview', op, {
      tables: 'a, b',
      table_include: '',
      table_exclude: '',
      extra: false,
      extra_detail: 'x',
    });
    const shown = Object.values(names(view)).flat();
    expect(shown).toContain('tables');
    expect(shown).not.toContain('table_include');
    expect(shown).not.toContain('extra_detail');
  });

  it('sin catálogo muestra todas las claves guardadas en una tarjeta', () => {
    const view = buildParamsView('documentation', undefined, { a: 1, b: true });
    expect(view.cards).toHaveLength(1);
    expect(view.cards[0]?.title).toBe('runs.cards.params');
    expect(names(view)).toEqual({ saved: ['b', 'a'] });
  });
});
