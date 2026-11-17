import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi } from '../../test/api';
import { stubEventSource } from '../../test/eventSource';
import {
  FINISHED,
  MIGRATION_PLAN,
  NOOP,
  ORACLE_CONNECTION,
  PLAN_ID,
  PLAN_RUN,
  PROJECT,
  RUN,
  RUN_ID,
} from '../../test/fixtures_runs';
import { chooseOperation } from '../../test/launch';
import { renderRoute } from '../../test/render';
import type { Operation } from './useRuns';

// Filtro de tablas por patrones en el plan de migración y la vista previa del volcado (1.19.0, util_bbdd 5.9.0).

const param = (
  name: string,
  type: Operation['params'][number]['type'],
  extra: Partial<Operation['params'][number]> = {},
): Operation['params'][number] => ({
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

const FILTER_PARAMS = [
  param('table_include', 'string', { group: 'filter' }),
  param('table_exclude', 'string', { group: 'filter' }),
];

const MIGRATE_PLAN: Operation = {
  name: 'migrate_plan',
  title: 'Plan de migración DDL',
  description: 'Plan',
  form: true,
  params: [
    param('source_connection', 'connection', { required: true }),
    param('source_schema', 'string'),
    param('target_engine', 'string', { required: true, options: ['mariadb', 'postgresql'] }),
    ...FILTER_PARAMS,
  ],
};

const DUMP_PREVIEW: Operation = {
  name: 'dump_preview',
  title: 'Volcado de datos: vista previa',
  description: 'Vista previa',
  form: true,
  params: [
    param('source_connection', 'connection', { required: true }),
    param('source_schema', 'string'),
    param('target_connection', 'connection', { required: true }),
    param('tables', 'string', { group: 'filter' }),
    ...FILTER_PARAMS,
  ],
};

function stubForm(operation: Operation) {
  stubEventSource();
  const base = `/api/v1/connections/${ORACLE_CONNECTION.connection_id}`;
  return stubApi({
    ...session(ADMIN),
    'GET /api/v1/projects/5': { body: PROJECT },
    'GET /api/v1/projects/5/runs': { body: { items: [], total: 0 } },
    'GET /api/v1/projects/5/connections': { body: [ORACLE_CONNECTION] },
    'GET /api/v1/operations': { body: [NOOP, operation] },
    [`GET ${base}/metadata/schemas`]: { body: { default: 'VENTAS', schemas: [] } },
    [`GET ${base}/metadata/schemas/VENTAS`]: {
      body: {
        engine: 'oracle',
        schema_name: 'VENTAS',
        database: null,
        fetched_at: '2026-11-16T10:00:00Z',
        size_bytes: 10,
        tables: ['MVG_PEDIDO', 'MVG_PEDIDO_BAK', 'COB_LINEA'].map((name) => ({
          name,
          comment: null,
          columns: 2,
        })),
        views: [{ name: 'MVG_V', comment: null, materialized: false }],
        routines: [],
      },
    },
    'POST /api/v1/projects/5/runs': { status: 202, body: { ...RUN, status: 'queued' } },
    [`GET /api/v1/runs/${RUN_ID}`]: { body: { ...RUN, status: 'queued', artifacts: [] } },
  });
}

async function openFilter(operation: Operation) {
  const user = userEvent.setup();
  renderRoute('/projects/5');
  await user.click(await screen.findByRole('button', { name: 'Lanzar ejecución' }));
  const dialog = await screen.findByRole('dialog');
  await chooseOperation(user, dialog, operation.title);
  await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Conexión origen' }), 'ventas');
  const filter = await within(dialog).findByRole('group', { name: 'Filtro de tablas' });
  // El volcado elige entre todas las tablas, una lista exacta o patrones (no se combinan).
  if (operation.name === 'dump_preview')
    await user.click(within(filter).getByRole('radio', { name: 'Patrones' }));
  await user.type(within(filter).getByRole('textbox', { name: 'Incluir (patrones)' }), 'mvg_*');
  await user.type(within(filter).getByRole('textbox', { name: 'Excluir (patrones)' }), '*_BAK');
  await user.click(within(filter).getByRole('button', { name: 'Probar patrones' }));
  return { user, dialog, filter };
}

describe('filtro de tablas del plan de migración', () => {
  it('prueba los patrones con tablas y vistas del origen y envía el filtro', async () => {
    const fetchMock = stubForm(MIGRATE_PLAN);
    const { user, dialog, filter } = await openFilter(MIGRATE_PLAN);

    expect(await within(filter).findByText('Se migran 1 de 3 tablas y 1 de 1 vistas.')).toBeInTheDocument();
    expect(within(filter).getByText('Se migran')).toBeInTheDocument();
    expect(within(filter).getByText('MVG_PEDIDO, MVG_V')).toBeInTheDocument();
    await user.click(within(filter).getByRole('button', { name: 'Cómo escribir los patrones' }));
    expect(within(filter).getByText(/se añaden al final del script/)).toBeInTheDocument();

    await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Motor destino' }), 'mariadb');
    await user.click(within(dialog).getByRole('button', { name: 'Lanzar' }));
    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')).toHaveLength(1));
    expect(await callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')[0]?.json()).toMatchObject({
      operation: 'migrate_plan',
      params: { source_connection: 'ventas', table_include: 'mvg_*', table_exclude: '*_BAK' },
    });
  });
});

describe('filtro de tablas de la vista previa del volcado', () => {
  it('prueba los patrones solo con las tablas (no vistas)', async () => {
    stubForm(DUMP_PREVIEW);
    const { user, filter } = await openFilter(DUMP_PREVIEW);

    expect(await within(filter).findByText('Se vuelcan 1 de 3 tablas.')).toBeInTheDocument();
    expect(within(filter).getByText('MVG_PEDIDO')).toBeInTheDocument();
    expect(within(filter).getByText('MVG_PEDIDO_BAK, COB_LINEA')).toBeInTheDocument();
    expect(within(filter).queryByText(/MVG_V/)).not.toBeInTheDocument();
    expect(within(filter).queryByRole('textbox', { name: 'Tablas (lista exacta)' })).not.toBeInTheDocument();

    // Con la lista exacta, los patrones se vacían y desaparecen (el backend no admite las dos cosas).
    await user.click(within(filter).getByRole('radio', { name: 'Lista exacta' }));
    expect(within(filter).getByRole('textbox', { name: 'Tablas (lista exacta)' })).toBeInTheDocument();
    expect(within(filter).queryByRole('textbox', { name: 'Incluir (patrones)' })).not.toBeInTheDocument();
    await user.click(within(filter).getByRole('radio', { name: 'Patrones' }));
    expect(within(filter).getByRole('textbox', { name: 'Incluir (patrones)' })).toHaveValue('');
  });
});

describe('filtro en los visores', () => {
  it('el plan muestra los patrones y la frontera', async () => {
    stubEventSource();
    stubApi({
      ...session(ADMIN),
      [`GET /api/v1/runs/${PLAN_ID}`]: { body: { ...PLAN_RUN, my_role: 'owner' } },
      [`GET /api/v1/runs/${PLAN_ID}/plan`]: {
        body: {
          ...MIGRATION_PLAN,
          filter: { include: ['MVG_*'], exclude: ['*_BAK'] },
          frontier: ['AUX_PAIS', 'COB_MONEDA'],
        },
      },
      'GET /api/v1/projects/5/connections': { body: [] },
      'GET /api/v1/projects/5/runs': { body: { items: [], total: 0 } },
    });

    renderRoute(`/runs/${PLAN_ID}`);

    const summary = (await screen.findByText('Filtro de tablas')).closest('[role="alert"]');
    expect(summary).not.toBeNull();
    const box = within(summary as HTMLElement);
    expect(box.getByText('MVG_*')).toBeInTheDocument();
    expect(box.getByText('*_BAK')).toBeInTheDocument();
    expect(box.getByText(/Frontera \(2 tablas de fuera/)).toHaveTextContent('AUX_PAIS, COB_MONEDA');
  });

  it('un plan sin filtro no muestra el resumen', async () => {
    stubEventSource();
    stubApi({
      ...session(ADMIN),
      [`GET /api/v1/runs/${PLAN_ID}`]: { body: { ...PLAN_RUN, my_role: 'owner' } },
      [`GET /api/v1/runs/${PLAN_ID}/plan`]: { body: MIGRATION_PLAN },
      'GET /api/v1/projects/5/connections': { body: [] },
      'GET /api/v1/projects/5/runs': { body: { items: [], total: 0 } },
    });

    renderRoute(`/runs/${PLAN_ID}`);

    expect(await screen.findByText('postgresql (public) → mysql')).toBeInTheDocument();
    expect(screen.queryByText('Filtro de tablas')).not.toBeInTheDocument();
  });

  it('la vista previa del volcado muestra los patrones', async () => {
    const previewId = '01JPREVPREVPREVPREVPREVPRE';
    stubEventSource();
    stubApi({
      ...session(ADMIN),
      [`GET /api/v1/runs/${previewId}`]: {
        body: {
          ...FINISHED,
          id: previewId,
          operation: 'dump_preview',
          finished_at: new Date().toISOString(),
          params: { source_connection: 'origen', target_connection: 'destino', table_include: 'MVG_*' },
          my_role: 'owner',
          artifacts: [],
        },
      },
      [`GET /api/v1/runs/${previewId}/dump-preview`]: {
        body: {
          source_engine: 'postgresql',
          target_engine: 'mysql',
          source_schema: 'public',
          target_schema: null,
          truncate_target: false,
          filter: { include: ['MVG_*'], exclude: [] },
          constraints_managed: true,
          load_order: ['mvg_pedido'],
          cycles: [],
          structure_hash: 'h'.repeat(64),
          tables: [
            {
              table: 'mvg_pedido',
              target_table: 'mvg_pedido',
              position: 0,
              in_cycle: false,
              source_rows: 2,
              target_rows: 0,
              skipped_columns: [],
              missing_target_columns: [],
              outside_references: ['cob_moneda'],
            },
          ],
        },
      },
      'GET /api/v1/projects/5/connections': { body: [] },
      'GET /api/v1/projects/5/runs': { body: { items: [], total: 0 } },
    });

    renderRoute(`/runs/${previewId}`);

    const summary = (await screen.findByText('Filtro de tablas')).closest('[role="alert"]');
    expect(within(summary as HTMLElement).getByText('MVG_*')).toBeInTheDocument();
    expect(within(summary as HTMLElement).queryByText(/Excluir/)).not.toBeInTheDocument();
  });
});
