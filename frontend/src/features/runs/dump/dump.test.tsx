import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, type StubResponse, stubApi } from '../../../test/api';
import { stubEventSource } from '../../../test/eventSource';
import { FINISHED, RUN } from '../../../test/fixtures_runs';
import { renderRoute } from '../../../test/render';
import type { DumpPreview, DumpResult } from './useDump';

const PREVIEW_ID = '01JPREVPREVPREVPREVPREVPRE';
const DUMP_ID = '01JDUMPDUMPDUMPDUMPDUMPDUM';
const ALLOWED = { ...ADMIN, can_write_data: true };

const PREVIEW: DumpPreview = {
  source_engine: 'postgresql',
  target_engine: 'mysql',
  source_schema: 'public',
  target_schema: null,
  truncate_target: false,
  constraints_managed: true,
  warnings: [],
  load_order: ['clientes', 'pedidos', 'a', 'b', 'sueltas'],
  cycles: [['a', 'b']],
  structure_hash: 'h'.repeat(64),
  tables: [
    { table: 'clientes', target_table: 'clientes', position: 0, in_cycle: false, source_rows: 2, target_rows: 3,
      skipped_columns: ['email'], missing_target_columns: [], outside_references: [], date_columns: [] },
    { table: 'pedidos', target_table: 'pedidos', position: 1, in_cycle: false, source_rows: 5, target_rows: 0,
      skipped_columns: [], missing_target_columns: ['alta'], outside_references: ['facturas'], date_columns: [] },
    { table: 'a', target_table: 'a', position: 2, in_cycle: true, source_rows: 1, target_rows: 0,
      skipped_columns: [], missing_target_columns: [], outside_references: [], date_columns: [] },
    { table: 'b', target_table: 'b', position: 3, in_cycle: true, source_rows: 1, target_rows: 0,
      skipped_columns: [], missing_target_columns: [], outside_references: [], date_columns: [] },
    { table: 'sueltas', target_table: null, position: 4, in_cycle: false, source_rows: 1, target_rows: null,
      skipped_columns: [], missing_target_columns: [], outside_references: [], date_columns: [] },
  ],
}; // prettier-ignore

const CONNECTIONS = [
  { id: 1, alias: 'origen', connection_id: 1, connection_name: 'Origen', db_type: 'postgresql', read_only: true,
    created_at: '2026-10-20T08:00:00Z' },
  { id: 2, alias: 'destino', connection_id: 2, connection_name: 'Destino', db_type: 'mysql', read_only: false,
    created_at: '2026-10-20T08:00:00Z' },
]; // prettier-ignore

function previewRun(overrides: Record<string, unknown> = {}) {
  return {
    ...FINISHED,
    id: PREVIEW_ID,
    operation: 'dump_preview',
    finished_at: new Date().toISOString(),
    params: { source_connection: 'origen', target_connection: 'destino' },
    my_role: 'owner',
    artifacts: [],
    ...overrides,
  };
}

function stubPreview({
  me = ALLOWED as object,
  preview = PREVIEW,
  run = previewRun(),
  connections = CONNECTIONS,
  post = { status: 202, body: { ...RUN, id: DUMP_ID, status: 'queued' } } as StubResponse,
} = {}) {
  stubEventSource();
  return stubApi({
    ...session(me),
    [`GET /api/v1/runs/${PREVIEW_ID}`]: { body: run },
    [`GET /api/v1/runs/${PREVIEW_ID}/dump-preview`]: { body: preview },
    'GET /api/v1/projects/5/connections': { body: connections },
    'GET /api/v1/projects/5/runs': { body: { items: [], total: 0 } },
    'POST /api/v1/projects/5/runs': post,
    [`GET /api/v1/runs/${DUMP_ID}`]: {
      body: { ...RUN, id: DUMP_ID, operation: 'dump_apply', status: 'queued', my_role: 'owner', artifacts: [],
              params: { preview_run: PREVIEW_ID, confirm: 'destino' } },
    }, // prettier-ignore
  });
}

async function openConfirm(user: ReturnType<typeof userEvent.setup>, label = /Volcar en «destino»/) {
  await user.click(await screen.findByRole('button', { name: label }));
  return screen.findByRole('dialog');
}

describe('vista previa del volcado', () => {
  it('muestra el orden, las notas por tabla y los avisos', async () => {
    stubPreview({
      preview: {
        ...PREVIEW,
        warnings: ['isolate_oracle', 'sqlite_dates'],
        tables: PREVIEW.tables.map((x) => (x.table === 'clientes' ? { ...x, date_columns: ['alta'] } : x)),
      },
    });

    renderRoute(`/runs/${PREVIEW_ID}`);

    const order = await screen.findByRole('table', { name: 'Orden de carga' });
    expect(within(order).getAllByRole('row')).toHaveLength(6);
    expect(within(order).getByText('no se copian: email')).toBeInTheDocument();
    expect(within(order).getAllByText('en ciclo')).toHaveLength(2);
    expect(within(order).getByText('no existe')).toBeInTheDocument();
    expect(screen.getByText(/No existen en el destino y no se cargarán: sueltas/)).toBeInTheDocument();
    expect(screen.getByText(/columnas obligatorias .* su carga fallará: pedidos/)).toBeInTheDocument();
    expect(screen.getByText(/ya tiene filas en clientes: se añadirán/)).toBeInTheDocument();
    expect(screen.getByText(/Hay 1 ciclo de FK/)).toBeInTheDocument();
    expect(
      screen.getByText(/«apartar» no aparta las filas con clave primaria duplicada/),
    ).toBeInTheDocument();
    expect(screen.getByText(/no carga fechas guardadas como texto.*clientes \(alta\)/)).toBeInTheDocument();
  });

  it('explica por qué no se puede volcar', async () => {
    stubPreview({ me: ADMIN });
    renderRoute(`/runs/${PREVIEW_ID}`);
    expect(await screen.findByText(/necesitas el permiso «Puede escribir datos»/)).toBeInTheDocument();
  });

  it('no se vuelca sobre un destino de solo lectura ni con una vista previa antigua', async () => {
    stubPreview({
      connections: [CONNECTIONS[0], { ...CONNECTIONS[1], read_only: true }] as typeof CONNECTIONS,
    });
    renderRoute(`/runs/${PREVIEW_ID}`);
    expect(await screen.findByText('La conexión destino «destino» es de solo lectura.')).toBeInTheDocument();
  });

  it('una vista previa de hace más de una hora pide repetirla', async () => {
    stubPreview({ run: previewRun({ finished_at: new Date(Date.now() - 61 * 60 * 1000).toISOString() }) });
    renderRoute(`/runs/${PREVIEW_ID}`);
    expect(await screen.findByText(/más de 60 minutos/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Volcar en/ })).not.toBeInTheDocument();
  });
});

describe('lanzar el volcado', () => {
  it('añadiendo: casilla y alias antes de enviar', async () => {
    const fetchMock = stubPreview();
    const user = userEvent.setup();

    renderRoute(`/runs/${PREVIEW_ID}`);
    const dialog = await openConfirm(user);
    const submit = within(dialog).getByRole('button', { name: 'Volcar ahora' });
    expect(within(dialog).queryByText('Se vaciará el destino')).not.toBeInTheDocument();
    expect(submit).toBeDisabled();
    await user.click(within(dialog).getByRole('checkbox', { name: /He revisado la vista previa/ }));
    await user.type(
      within(dialog).getByRole('textbox', { name: 'Escribe «destino» para confirmar' }),
      'destino',
    );
    await user.click(submit);

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')).toHaveLength(1));
    expect(await callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')[0]?.json()).toEqual({
      operation: 'dump_apply',
      params: { preview_run: PREVIEW_ID, confirm: 'destino' },
    });
  });

  it('vaciando: muestra las filas que se borran y exige «VACIAR»', async () => {
    const fetchMock = stubPreview({ preview: { ...PREVIEW, truncate_target: true } });
    const user = userEvent.setup();

    renderRoute(`/runs/${PREVIEW_ID}`);
    const dialog = await openConfirm(user, /Vaciar y volcar en «destino»/);
    expect(
      within(dialog).getByText('Se borrarán 3 filas que ya existen en las tablas destino.'),
    ).toBeInTheDocument();
    await user.click(within(dialog).getByRole('checkbox', { name: /He revisado la vista previa/ }));
    await user.type(
      within(dialog).getByRole('textbox', { name: 'Escribe «destino» para confirmar' }),
      'destino',
    );
    const submit = within(dialog).getByRole('button', { name: 'Volcar ahora' });
    expect(submit).toBeDisabled();
    await user.type(within(dialog).getByRole('textbox', { name: /Escribe «VACIAR»/ }), 'VACIAR');
    await user.click(submit);

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')).toHaveLength(1));
    expect(await callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')[0]?.json()).toMatchObject({
      params: { preview_run: PREVIEW_ID, confirm: 'destino', confirm_truncate: 'VACIAR' },
    });
  });

  it('el error de la API se ve dentro del modal', async () => {
    stubPreview({
      post: { status: 409, body: { title: 'Conflicto', status: 409, detail: 'Ya hay un volcado en curso.' } },
    });
    const user = userEvent.setup();

    renderRoute(`/runs/${PREVIEW_ID}`);
    const dialog = await openConfirm(user);
    await user.click(within(dialog).getByRole('checkbox', { name: /He revisado la vista previa/ }));
    await user.type(
      within(dialog).getByRole('textbox', { name: 'Escribe «destino» para confirmar' }),
      'destino',
    );
    await user.click(within(dialog).getByRole('button', { name: 'Volcar ahora' }));

    expect(await within(dialog).findByText('Ya hay un volcado en curso.')).toBeInTheDocument();
  });
});

describe('resultado del volcado', () => {
  const RESULT: DumpResult = {
    load_order: ['clientes', 'pedidos'],
    cycles: [],
    report: true,
    tables: [
      { table: 'clientes', status: 'success', source_rows: 2, target_rows_before: 0, target_rows_after: 1,
        rows_rejected: 1, skipped_columns: [], position: 0, in_cycle: false, error: null },
      { table: 'pedidos', status: 'error', source_rows: 5, target_rows_before: 0, target_rows_after: 0,
        rows_rejected: 0, skipped_columns: [], position: 1, in_cycle: false,
        error: 'NOT NULL constraint failed: pedidos.alta' },
    ],
    constraints: [{ table: 'pedidos', constraint: 'fk_cli', status: 'failed', error: 'orphan rows' }],
    pk_sync: [],
    cancelled: false,
    completed_tables: [],
  }; // prettier-ignore

  it('muestra filas, rechazos y constraints sin reactivar, sin relanzar ni cancelar', async () => {
    stubEventSource();
    stubApi({
      ...session(ALLOWED),
      [`GET /api/v1/runs/${DUMP_ID}`]: {
        body: {
          ...FINISHED, id: DUMP_ID, operation: 'dump_apply', status: 'failed', my_role: 'owner',
          error_code: 'dump_partial', error_message: 'Volcado incompleto',
          params: { preview_run: PREVIEW_ID, confirm: 'destino' },
          artifacts: [{ id: 9, path: 'outputs/rejects/rechazos.csv', kind: 'rejects', mime: 'text/csv',
                        size_bytes: 10, sha256: 'a'.repeat(64), created_at: '2026-10-20T08:00:04Z', previewable: false }],
        },
      },
      [`GET /api/v1/runs/${DUMP_ID}/dump-result`]: { body: RESULT },
    }); // prettier-ignore

    renderRoute(`/runs/${DUMP_ID}`);

    const tables = await screen.findByRole('table', { name: 'Tablas volcadas' });
    expect(within(tables).getByText('NOT NULL constraint failed: pedidos.alta')).toBeInTheDocument();
    expect(screen.getByRole('table', { name: 'Constraints que no se reactivaron' })).toHaveTextContent(
      'pedidos.fk_cli',
    );
    expect(screen.getByText('Hay filas apartadas')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ver la vista previa' })).toHaveAttribute(
      'href',
      `/runs/${PREVIEW_ID}`,
    );
    expect(screen.queryByRole('button', { name: 'Relanzar' })).not.toBeInTheDocument();
  });

  it('un volcado cancelado lista las tablas que quedaron cargadas', async () => {
    stubEventSource();
    stubApi({
      ...session(ALLOWED),
      [`GET /api/v1/runs/${DUMP_ID}`]: {
        body: {
          ...FINISHED, id: DUMP_ID, operation: 'dump_apply', status: 'cancelled', my_role: 'owner',
          error_code: 'cancelled', params: { preview_run: PREVIEW_ID, confirm: 'destino' }, artifacts: [],
        },
      },
      [`GET /api/v1/runs/${DUMP_ID}/dump-result`]: {
        body: { ...RESULT, report: false, tables: [], constraints: [], cancelled: true, completed_tables: ['clientes'] },
      },
    }); // prettier-ignore

    renderRoute(`/runs/${DUMP_ID}`);

    expect(await screen.findByText('Cancelado entre lotes')).toBeInTheDocument();
    expect(screen.getByText(/Se cargó 1 tabla antes de cancelar/)).toBeInTheDocument();
    expect(screen.getByText('clientes')).toBeInTheDocument();
    expect(screen.queryByRole('table', { name: 'Tablas volcadas' })).not.toBeInTheDocument();
    expect(screen.queryByText(/No se pudo generar el informe Excel/)).not.toBeInTheDocument();
  });

  it('un volcado en curso se cancela entre lotes tras confirmarlo', async () => {
    stubEventSource();
    const running = {
      ...RUN, id: DUMP_ID, operation: 'dump_apply', status: 'running', my_role: 'owner', artifacts: [],
      params: { preview_run: PREVIEW_ID, confirm: 'destino' },
    }; // prettier-ignore
    const fetchMock = stubApi({
      ...session(ALLOWED),
      [`GET /api/v1/runs/${DUMP_ID}`]: { body: running },
      [`POST /api/v1/runs/${DUMP_ID}/cancel`]: { status: 202, body: { ...running, cancel_requested: true } },
    });
    const user = userEvent.setup();

    renderRoute(`/runs/${DUMP_ID}`);

    await user.click(await screen.findByRole('button', { name: 'Cancelar' }));
    const dialog = await screen.findByRole('dialog', { name: 'Cancelar el volcado' });
    expect(within(dialog).getByText(/las tablas ya terminadas quedan cargadas/)).toBeInTheDocument();
    expect(callsTo(fetchMock, 'POST', `/api/v1/runs/${DUMP_ID}/cancel`)).toHaveLength(0);
    await user.click(within(dialog).getByRole('button', { name: 'Cancelar entre lotes' }));
    await waitFor(() => expect(callsTo(fetchMock, 'POST', `/api/v1/runs/${DUMP_ID}/cancel`)).toHaveLength(1));
    expect(screen.queryByText(/no se puede cancelar/)).not.toBeInTheDocument();
  });
});

describe('constraints sin restaurar', () => {
  const RESTORE_ID = '01JRESTRESTRESTRESTRESTRES';
  const PENDING = {
    pending: true, engine: 'mysql', target_connection: 'destino', tables: ['clientes', 'pedidos'], constraints: [],
    created_at: '2026-10-27T08:00:00+00:00', restore_run: null,
  }; // prettier-ignore

  function stubInterrupted(me: object, pending: object = PENDING) {
    stubEventSource();
    return stubApi({
      ...session(me),
      [`GET /api/v1/runs/${DUMP_ID}`]: {
        body: {
          ...FINISHED, id: DUMP_ID, operation: 'dump_apply', status: 'failed', my_role: 'owner',
          error_code: 'job_timeout', params: { preview_run: PREVIEW_ID, confirm: 'destino' }, artifacts: [],
        },
      },
      [`GET /api/v1/runs/${DUMP_ID}/dump-constraints`]: { body: pending },
      'GET /api/v1/projects/5/connections': { body: CONNECTIONS },
      'POST /api/v1/projects/5/runs': { status: 202, body: { ...RUN, id: RESTORE_ID, status: 'queued' } },
      [`GET /api/v1/runs/${RESTORE_ID}`]: {
        body: { ...RUN, id: RESTORE_ID, operation: 'dump_restore', status: 'queued', artifacts: [],
                params: { dump_run: DUMP_ID, confirm: 'destino' } },
      },
    }); // prettier-ignore
  }

  it('el owner con permiso las restaura escribiendo el alias', async () => {
    const fetchMock = stubInterrupted(ALLOWED);
    const user = userEvent.setup();

    renderRoute(`/runs/${DUMP_ID}`);

    expect(await screen.findByText('Constraints sin restaurar')).toBeInTheDocument();
    expect(
      screen.getByText(/dejó 2 objetos con las constraints desactivadas en «destino»/),
    ).toBeInTheDocument();
    expect(screen.getByText('pedidos')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Restaurar constraints…' }));
    const dialog = await screen.findByRole('dialog', { name: 'Restaurar constraints' });
    const submit = within(dialog).getByRole('button', { name: 'Restaurar ahora' });
    expect(submit).toBeDisabled();
    await user.type(
      within(dialog).getByRole('textbox', { name: 'Escribe «destino» para confirmar' }),
      'destino',
    );
    await user.click(submit);

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')).toHaveLength(1));
    expect(await callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')[0]?.json()).toEqual({
      operation: 'dump_restore',
      params: { dump_run: DUMP_ID, confirm: 'destino' },
    });
  });

  it('sin permiso se explica el motivo; con una restauración en marcha, se enlaza', async () => {
    stubInterrupted(ADMIN);

    const view = renderRoute(`/runs/${DUMP_ID}`);

    expect(await screen.findByText(/necesitas el permiso «Puede escribir datos»/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Restaurar constraints…' })).not.toBeInTheDocument();
    view.unmount();

    stubInterrupted(ALLOWED, { ...PENDING, restore_run: RESTORE_ID });
    renderRoute(`/runs/${DUMP_ID}`);

    expect(
      await screen.findByRole('link', { name: 'Hay una restauración en marcha: ver la ejecución' }),
    ).toHaveAttribute('href', `/runs/${RESTORE_ID}`);
  });
});
