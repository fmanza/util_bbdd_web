import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi } from '../../../test/api';
import { stubEventSource } from '../../../test/eventSource';
import { DOCUMENTATION, NOOP, ORACLE_CONNECTION, PROJECT, RUN } from '../../../test/fixtures_runs';
import { chooseOperation } from '../../../test/launch';
import { renderRoute } from '../../../test/render';
import type { Operation } from '../useRuns';
import { categorize, LAUNCH_LAYOUTS, resolveCards } from './launchLayout';

type Param = Operation['params'][number];

const param = (name: string, type: Param['type'], extra: Partial<Param> = {}): Param => ({
  name,
  type,
  required: false,
  default: null,
  description: name,
  minimum: null,
  maximum: null,
  options: null,
  group: null,
  ...extra,
});

const operation = (name: string, params: Param[], title = name): Operation => ({
  name,
  title,
  description: `${title}: descripción`,
  form: true,
  params,
});

const DUMP_PREVIEW = operation(
  'dump_preview',
  [
    param('source_connection', 'connection', { required: true }),
    param('target_connection', 'connection', { required: true }),
    param('tables', 'string', { group: 'filter' }),
    param('table_include', 'string', { group: 'filter' }),
    param('table_exclude', 'string', { group: 'filter' }),
    param('truncate_target', 'boolean', { default: false, group: 'load' }),
    param('on_error', 'string', { default: 'raise', group: 'errors', options: ['raise', 'isolate'] }),
    param('max_rejects', 'integer', { group: 'errors', minimum: 1, maximum: 1000 }),
    param('chunk_size', 'integer', { default: 5000, group: 'performance', minimum: 100, maximum: 100000 }),
  ],
  'Volcado de datos: vista previa',
);

const COMPARE = operation(
  'compare',
  [
    param('source_connection', 'connection', { required: true }),
    param('target_connection', 'connection', { required: true }),
    param('tables', 'boolean', { default: true, group: 'scope' }),
    param('indexes', 'boolean', { default: true, group: 'scope', requires: 'tables' }),
    param('views', 'boolean', { default: true, group: 'scope' }),
    param('sql', 'boolean', { default: true, group: 'reports' }),
    param('sql_dialect', 'string', {
      default: 'auto',
      group: 'reports',
      requires: 'sql',
      options: ['auto', 'generic'],
    }),
  ],
  'Comparación de esquemas',
);

function stubLaunch(operations: Operation[]) {
  stubEventSource();
  return stubApi({
    ...session(ADMIN),
    'GET /api/v1/projects/5': { body: PROJECT },
    'GET /api/v1/projects/5/runs': { body: { items: [], total: 0 } },
    'GET /api/v1/projects/5/connections': { body: [ORACLE_CONNECTION] },
    'GET /api/v1/operations': { body: operations },
    'POST /api/v1/projects/5/runs': { status: 202, body: { ...RUN, status: 'queued' } },
    [`GET /api/v1/runs/${RUN.id}`]: { body: { ...RUN, status: 'queued', artifacts: [] } },
  });
}

async function openLaunch() {
  const user = userEvent.setup();
  renderRoute('/projects/5');
  await user.click(await screen.findByRole('button', { name: 'Lanzar ejecución' }));
  const dialog = await screen.findByRole('dialog');
  await within(dialog).findByRole('radiogroup', { name: 'Operación' });
  return { user, dialog };
}

async function postedParams(fetchMock: ReturnType<typeof stubApi>) {
  await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')).toHaveLength(1));
  const body = (await callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')[0]?.json()) as {
    params: Record<string, unknown>;
  };
  return body.params;
}

describe('diseño de las tarjetas', () => {
  it('coloca cada parámetro una sola vez y manda los desconocidos a «Otros»', () => {
    const op = { ...DOCUMENTATION, params: [...DOCUMENTATION.params, param('nuevo', 'boolean')] };
    const cards = resolveCards(op);
    const placed = cards.flatMap((card) => card.params);
    expect([...placed].sort()).toEqual(op.params.map((p) => p.name).sort());
    expect(new Set(placed).size).toBe(placed.length);
    expect(cards.at(-1)).toMatchObject({ id: 'other', params: ['nuevo'] });
  });

  it('no repite un parámetro entre tarjetas del diseño', () => {
    for (const [name, specs] of Object.entries(LAUNCH_LAYOUTS)) {
      const names = specs.flatMap((spec) =>
        spec.items.flatMap((item) => (typeof item === 'string' ? [item] : 'stack' in item ? item.stack : [])),
      );
      expect(new Set(names).size, name).toBe(names.length);
    }
  });

  it('sin diseño propio, una tarjeta por grupo', () => {
    const cards = resolveCards(
      operation('futura', [param('a', 'string'), param('b', 'boolean', { group: 'formats' })]),
    );
    expect(cards.map((c) => [c.id, c.params])).toEqual([
      ['main', ['a']],
      ['group-formats', ['b']],
    ]);
  });

  it('ordena las operaciones por intención: documentar primero, diagnóstico al final', () => {
    const ops = [NOOP, operation('futura', []), DUMP_PREVIEW, DOCUMENTATION, COMPARE];
    expect(categorize(ops).map((c) => [c.key, c.operations.map((o) => o.name)])).toEqual([
      ['document', ['documentation']],
      ['compare', ['compare']],
      ['move', ['dump_preview']],
      ['other', ['futura']],
      ['diagnostics', ['noop']],
    ]);
  });
});

describe('modal «Lanzar ejecución»', () => {
  it('elige la documentación al abrir, no la prueba del motor', async () => {
    stubLaunch([NOOP, DOCUMENTATION]);
    const { dialog } = await openLaunch();

    expect(within(dialog).getByRole('radio', { name: 'Documentación de la base de datos' })).toBeChecked();
    expect(within(dialog).getByRole('radio', { name: 'Prueba del motor de ejecuciones' })).not.toBeChecked();
    expect(within(dialog).getByRole('group', { name: 'Origen' })).toBeInTheDocument();
    expect(within(dialog).getByText('Solo lee la conexión.')).toBeInTheDocument();
  });

  it('oculta las opciones que dependen de un interruptor de la misma tarjeta y no las envía', async () => {
    const fetchMock = stubLaunch([COMPARE]);
    const { user, dialog } = await openLaunch();

    expect(within(dialog).getByRole('group', { name: 'Origen (referencia)' })).toBeInTheDocument();
    expect(within(dialog).getByRole('group', { name: 'Destino (se compara)' })).toBeInTheDocument();
    const reports = within(dialog).getByRole('group', { name: 'Informes' });
    expect(within(reports).getByRole('combobox', { name: 'Dialecto SQL' })).toBeInTheDocument();
    await user.click(within(reports).getByRole('switch', { name: /^Script SQL/ }));
    expect(within(reports).queryByRole('combobox', { name: 'Dialecto SQL' })).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole('switch', { name: /^Tablas y columnas/ }));
    expect(within(dialog).queryByRole('switch', { name: /^Índices/ })).not.toBeInTheDocument();

    const [source, target] = within(dialog).getAllByRole('combobox', { name: /^Conexión/ });
    await user.selectOptions(source as HTMLElement, 'ventas');
    await user.selectOptions(target as HTMLElement, 'ventas');
    await user.click(within(dialog).getByRole('button', { name: 'Lanzar' }));

    const params = await postedParams(fetchMock);
    expect(params).toMatchObject({ tables: false, sql: false, views: true });
    expect(params).not.toHaveProperty('sql_dialect');
    expect(params).not.toHaveProperty('indexes');
  });

  it('volcado: los rechazos máximos solo con «apartar» y las avanzadas se abren con un error', async () => {
    const fetchMock = stubLaunch([DUMP_PREVIEW]);
    const { user, dialog } = await openLaunch();
    await chooseOperation(user, dialog, 'Volcado de datos: vista previa');

    expect(within(dialog).getByText('Se vuelcan todas las tablas del schema origen.')).toBeInTheDocument();
    expect(
      within(dialog).queryByRole('textbox', { name: 'Rechazos máximos por tabla' }),
    ).not.toBeInTheDocument();
    const onError = within(dialog).getByRole('combobox', { name: 'Filas que el destino no admite' });
    await user.selectOptions(onError, 'isolate');
    await user.type(within(dialog).getByRole('textbox', { name: 'Rechazos máximos por tabla' }), '50');

    await user.click(within(dialog).getByRole('switch', { name: /^Vaciar el destino/ }));
    expect(within(dialog).getByText('Se vaciarán las tablas destino antes de cargar.')).toBeInTheDocument();

    const toggle = within(dialog).getByRole('button', { name: /Opciones avanzadas/ });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await user.click(toggle);
    const chunk = within(dialog).getByRole('textbox', { name: 'Filas por lote' });
    await user.clear(chunk);
    await user.type(chunk, '5');
    await user.click(toggle);
    expect(within(dialog).queryByRole('textbox', { name: 'Filas por lote' })).not.toBeInTheDocument();

    const [source, target] = within(dialog).getAllByRole('combobox', { name: /^Conexión/ });
    await user.selectOptions(source as HTMLElement, 'ventas');
    await user.selectOptions(target as HTMLElement, 'ventas');
    await user.click(within(dialog).getByRole('button', { name: 'Lanzar' }));

    // El único error está en una opción plegada: se abre la sección y el campo recibe el foco.
    const reopened = await within(dialog).findByRole('textbox', { name: 'Filas por lote' });
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(reopened).toHaveFocus();
    expect(within(dialog).getByText('Entre 100 y 100000')).toBeInTheDocument();
    expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')).toHaveLength(0);

    await user.clear(reopened);
    await user.type(reopened, '500');
    await user.selectOptions(onError, 'raise');
    await user.click(within(dialog).getByRole('button', { name: 'Lanzar' }));
    const params = await postedParams(fetchMock);
    expect(params).toMatchObject({ on_error: 'raise', chunk_size: 500, truncate_target: true });
    expect(params).not.toHaveProperty('max_rejects');
  });
});
