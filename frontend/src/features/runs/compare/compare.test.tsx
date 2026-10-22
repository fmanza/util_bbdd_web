import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi } from '../../../test/api';
import { stubEventSource } from '../../../test/eventSource';
import {
  COMPARE_RUN,
  EVOLUTION,
  FINISHED,
  OLD_COMPARE_ID,
  RUN_ID,
  SCHEMA_DIFF,
} from '../../../test/fixtures_runs';
import { renderRoute } from '../../../test/render';
import { toRows } from './diffRows';

function stubCompare(extra: Record<string, Parameters<typeof stubApi>[0][string]> = {}) {
  stubEventSource();
  return stubApi({
    ...session(ADMIN),
    [`GET /api/v1/runs/${RUN_ID}`]: { body: COMPARE_RUN },
    [`GET /api/v1/runs/${RUN_ID}/diff`]: { body: SCHEMA_DIFF },
    [`GET /api/v1/runs/${RUN_ID}/artifacts/43/preview`]: { text: 'CREATE TABLE facturas (id INT);' },
    'GET /api/v1/projects/5/runs': {
      body: {
        items: [
          { ...COMPARE_RUN, id: RUN_ID },
          { ...FINISHED, operation: 'compare', id: OLD_COMPARE_ID, created_at: '2026-10-01T08:00:00Z' },
        ],
        total: 2,
      },
    },
    ...extra,
  });
}

describe('visor del diff', () => {
  it('resume, filtra y despliega las diferencias de tablas', async () => {
    stubCompare();
    const user = userEvent.setup();

    renderRoute(`/runs/${RUN_ID}`);

    expect(await screen.findByRole('heading', { name: 'Diferencias de esquema' })).toBeInTheDocument();
    expect((await screen.findByText('Tablas solo en origen')).nextSibling).toHaveTextContent('1');
    expect(screen.getByRole('tab', { name: 'Tablas (3)' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Vistas (1)' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /clientes/ }));
    expect(await screen.findByRole('cell', { name: 'Nulos' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'ix_clientes_nombre' })).toBeInTheDocument();

    await user.selectOptions(screen.getByRole('combobox', { name: 'Estado' }), 'removed');
    expect(screen.getByRole('button', { name: /auditoria/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /facturas/ })).not.toBeInTheDocument();
    await user.selectOptions(screen.getByRole('combobox', { name: 'Estado' }), 'all');
    await user.type(screen.getByRole('textbox', { name: 'Filtrar por nombre' }), 'fact');
    expect(screen.getByRole('button', { name: /facturas/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /auditoria/ })).not.toBeInTheDocument();
  });

  it('muestra la definición de una vista lado a lado y avisa del script SQL', async () => {
    stubCompare();
    const user = userEvent.setup();

    renderRoute(`/runs/${RUN_ID}`);
    await user.click(await screen.findByRole('tab', { name: 'Vistas (1)' }));
    await user.click(screen.getByRole('button', { name: /v_clientes/ }));

    const table = await screen.findByRole('table', { name: 'Definición: 2 líneas distintas' });
    expect(within(table).getByRole('columnheader', { name: 'Origen' })).toBeInTheDocument();
    expect(within(table).getByText('nombre', { exact: false })).toBeInTheDocument();
    expect(screen.getByText('El script SQL no se ha ejecutado')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Informes de la comparación' })).toBeInTheDocument();
    expect(screen.getByTitle('Informe HTML de la comparación')).toHaveAttribute(
      'sandbox',
      'allow-scripts allow-popups allow-downloads',
    );
  });

  it('compara con otra ejecución y avisa si origen o destino difieren', async () => {
    const fetchMock = stubCompare({
      [`GET /api/v1/runs/${RUN_ID}/diff/evolution`]: { body: EVOLUTION },
    });
    const user = userEvent.setup();

    renderRoute(`/runs/${RUN_ID}`);
    const select = await screen.findByRole('combobox', { name: 'Comparación anterior' });
    expect(
      within(select).queryByRole('option', { name: new RegExp(RUN_ID.slice(-8)) }),
    ).not.toBeInTheDocument();
    await user.selectOptions(select, OLD_COMPARE_ID);

    expect(await screen.findByText('Origen o destino distintos')).toBeInTheDocument();
    expect(screen.getByRole('table', { name: 'Nuevas' })).toHaveTextContent('clientes.nombre (Nulos)');
    expect(screen.getByRole('table', { name: 'Resueltas' })).toHaveTextContent('pedidos');
    await waitFor(() => {
      const call = callsTo(fetchMock, 'GET', `/api/v1/runs/${RUN_ID}/diff/evolution`)[0];
      expect(call && new URL(call.url).searchParams.get('baseline')).toBe(OLD_COMPARE_ID);
    });
  });

  it('sin diferencias lo dice', async () => {
    stubCompare({
      [`GET /api/v1/runs/${RUN_ID}/diff`]: {
        body: {
          ...SCHEMA_DIFF,
          has_differences: false,
          table_diffs: [],
          view_diffs: [],
          summary: 'Sin diferencias',
        },
      },
    });

    renderRoute(`/runs/${RUN_ID}`);

    expect(await screen.findByText('Los dos esquemas son iguales en lo comparado.')).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: /Tablas/ })).not.toBeInTheDocument();
  });
});

describe('toRows', () => {
  it('empareja bloques eliminados y añadidos y rellena el lado corto', () => {
    const rows = toRows([
      { value: 'a\n' },
      { value: 'b\nc\n', removed: true },
      { value: 'B\n', added: true },
      { value: 'd\n', added: true },
    ]);

    expect(rows).toEqual([
      { source: { text: 'a', changed: false }, target: { text: 'a', changed: false } },
      { source: { text: 'b', changed: true }, target: { text: 'B', changed: true } },
      { source: { text: 'c', changed: true }, target: null },
      { source: null, target: { text: 'd', changed: true } },
    ]);
  });
});
