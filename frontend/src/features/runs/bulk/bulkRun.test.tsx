import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, type StubResponse, stubApi } from '../../../test/api';
import { stubEventSource } from '../../../test/eventSource';
import { FINISHED, RUN } from '../../../test/fixtures_runs';
import { renderRoute } from '../../../test/render';
import type { BulkPreview, BulkResult } from '../../bulk/useBulk';

const PREVIEW_ID = '01JPREVPREVPREVPREVPREVPRE';
const APPLY_ID = '01JBULKBULKBULKBULKBULKBUL';
const ALLOWED = { ...ADMIN, can_write_data: true };

const PREVIEW: BulkPreview = {
  table: 'clientes',
  schema: 'public',
  operation: 'insert',
  rows: 3,
  columns: ['id', 'nombre'],
  mapping: { ID: 'id', nombre: 'nombre' },
  ignored_columns: ['notas'],
  primary_key: ['id'],
  errors: [],
  matches: 0,
  target_rows: 10,
  parallel: { workers: 1, reasons: [] },
  sample: [['1', 'Ana'], ['2', null]],
  sql_file: 'sql/carga_insert.sql',
  structure_hash: 'h'.repeat(64),
  target_engine: 'postgresql',
  upload_filename: 'clientes.csv',
}; // prettier-ignore

const SQL_ARTIFACT = {
  id: 3, path: 'outputs/sql/carga_insert.sql', kind: 'sql', mime: 'text/plain', size_bytes: 80,
  sha256: 'b'.repeat(64), created_at: '2026-10-23T08:00:00Z', previewable: true,
}; // prettier-ignore

const CONNECTIONS = [
  { id: 2, alias: 'destino', connection_id: 2, connection_name: 'Destino', db_type: 'postgresql', read_only: false,
    created_at: '2026-10-20T08:00:00Z' },
]; // prettier-ignore

function previewRun(overrides: Record<string, unknown> = {}) {
  return {
    ...FINISHED,
    id: PREVIEW_ID,
    operation: 'bulk_preview',
    finished_at: new Date().toISOString(),
    params: { target_connection: 'destino', table: 'clientes' },
    my_role: 'owner',
    artifacts: [SQL_ARTIFACT],
    ...overrides,
  };
}

function stubPreview({
  me = ALLOWED as object,
  preview = PREVIEW,
  post = { status: 202, body: { ...RUN, id: APPLY_ID, status: 'queued' } } as StubResponse,
} = {}) {
  stubEventSource();
  return stubApi({
    ...session(me),
    [`GET /api/v1/runs/${PREVIEW_ID}`]: { body: previewRun() },
    [`GET /api/v1/runs/${PREVIEW_ID}/bulk-preview`]: { body: preview },
    [`GET /api/v1/runs/${PREVIEW_ID}/artifacts/3/preview`]: {
      text: "INSERT INTO public.clientes (id, nombre) VALUES (1, 'Ana');\n",
    },
    'GET /api/v1/projects/5/connections': { body: CONNECTIONS },
    'GET /api/v1/projects/5/runs': { body: { items: [], total: 0 } },
    'POST /api/v1/projects/5/runs': post,
    [`GET /api/v1/runs/${APPLY_ID}`]: {
      body: { ...RUN, id: APPLY_ID, operation: 'bulk_apply', status: 'queued', my_role: 'owner', artifacts: [],
              params: { preview_run: PREVIEW_ID, confirm: 'destino' } },
    }, // prettier-ignore
  });
}

async function confirmBase(user: ReturnType<typeof userEvent.setup>, label: RegExp) {
  await user.click(await screen.findByRole('button', { name: label }));
  const dialog = await screen.findByRole('dialog');
  await user.click(within(dialog).getByRole('checkbox', { name: /He revisado la vista previa/ }));
  await user.type(
    within(dialog).getByRole('textbox', { name: 'Escribe «destino» para confirmar' }),
    'destino',
  );
  return dialog;
}

describe('vista previa de la carga', () => {
  it('muestra cifras, muestra de filas, columnas ignoradas y el SQL generado', async () => {
    stubPreview();
    renderRoute(`/runs/${PREVIEW_ID}`);

    expect(
      await screen.findByText('Insertar «clientes.csv» en public.clientes (destino)'),
    ).toBeInTheDocument();
    const sample = screen.getByRole('table', { name: 'Primeras filas' });
    expect(within(sample).getAllByRole('row')).toHaveLength(3);
    expect(screen.getByText('Columnas del fichero que no se cargan: notas.')).toBeInTheDocument();
    expect(await screen.findByText(/INSERT INTO public\.clientes/)).toBeInTheDocument();
  });

  it('con errores de validación no deja cargar', async () => {
    stubPreview({ preview: { ...PREVIEW, errors: ['Faltan columnas obligatorias: alta'] } });
    renderRoute(`/runs/${PREVIEW_ID}`);

    expect(await screen.findByText('Faltan columnas obligatorias: alta')).toBeInTheDocument();
    expect(screen.getByText(/La vista previa tiene errores/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Insertar en/ })).not.toBeInTheDocument();
  });

  it('explica por qué no se puede cargar sin el permiso', async () => {
    stubPreview({ me: ADMIN });
    renderRoute(`/runs/${PREVIEW_ID}`);
    expect(await screen.findByText(/necesitas el permiso «Puede escribir datos»/)).toBeInTheDocument();
  });
});

describe('lanzar la carga', () => {
  it('insertar: casilla y alias', async () => {
    const fetchMock = stubPreview();
    const user = userEvent.setup();

    renderRoute(`/runs/${PREVIEW_ID}`);
    const dialog = await confirmBase(user, /Insertar en «destino»/);
    expect(within(dialog).queryByRole('textbox', { name: /número de filas/ })).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Cargar ahora' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')).toHaveLength(1));
    expect(await callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')[0]?.json()).toEqual({
      operation: 'bulk_apply',
      params: { preview_run: PREVIEW_ID, confirm: 'destino' },
    });
  });

  it('borrar: exige escribir el número exacto de filas afectadas', async () => {
    const fetchMock = stubPreview({ preview: { ...PREVIEW, operation: 'delete', matches: 2 } });
    const user = userEvent.setup();

    renderRoute(`/runs/${PREVIEW_ID}`);
    expect(await screen.findByText('Filas que se borrarán')).toBeInTheDocument();
    const dialog = await confirmBase(user, /Borrar en «destino»/);
    expect(within(dialog).getByText('Se borrarán 2 filas')).toBeInTheDocument();
    const submit = within(dialog).getByRole('button', { name: 'Cargar ahora' });
    const rows = within(dialog).getByRole('textbox', { name: 'Escribe el número de filas afectadas' });
    await user.type(rows, '3');
    expect(submit).toBeDisabled();
    await user.clear(rows);
    await user.type(rows, '2');
    await user.click(submit);

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')).toHaveLength(1));
    expect(await callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')[0]?.json()).toEqual({
      operation: 'bulk_apply',
      params: { preview_run: PREVIEW_ID, confirm: 'destino', confirm_rows: 2 },
    });
  });

  it.each([
    ['ParallelPlan.atomic', { workers: 4, reasons: ['Más de 100 000 filas'], atomic: false }],
    ['vista previa anterior a la 1.5.0', { workers: 4, reasons: ['Más de 100 000 filas'] }],
  ])('en paralelo (%s): exige aceptar que no es atómica', async (_case, parallel) => {
    const fetchMock = stubPreview({ preview: { ...PREVIEW, parallel } });
    const user = userEvent.setup();

    renderRoute(`/runs/${PREVIEW_ID}`);
    expect(await screen.findByText('Plan paralelo de 4 hilos: no es atómico')).toBeInTheDocument();
    const dialog = await confirmBase(user, /Insertar en «destino»/);
    const submit = within(dialog).getByRole('button', { name: 'Cargar ahora' });
    expect(submit).toBeDisabled();
    await user.click(within(dialog).getByRole('checkbox', { name: /con 4 hilos no es atómica/ }));
    await user.click(submit);

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')).toHaveLength(1));
    expect(await callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')[0]?.json()).toMatchObject({
      params: { accept_non_atomic: true },
    });
  });

  it('el error de la API se ve dentro del modal', async () => {
    stubPreview({
      post: {
        status: 409,
        body: { title: 'Conflicto', status: 409, detail: 'Ya hay una escritura en curso.' },
      },
    });
    const user = userEvent.setup();

    renderRoute(`/runs/${PREVIEW_ID}`);
    const dialog = await confirmBase(user, /Insertar en «destino»/);
    await user.click(within(dialog).getByRole('button', { name: 'Cargar ahora' }));
    expect(await within(dialog).findByText('Ya hay una escritura en curso.')).toBeInTheDocument();
  });
});

describe('resultado de la carga', () => {
  const RESULT: BulkResult = {
    operation: 'insert',
    table: 'clientes',
    rows: 3,
    committed: 3,
    matches: 0,
    target_rows_before: 10,
    target_rows_after: 12,
    verified: null,
    rejected: 1,
    cancelled: false,
    error: null,
    parallel: { workers: 2, reasons: [] },
    partitions: [
      { index: 0, rows: 2, error: null },
      { index: 1, rows: 1, error: 'duplicate key' },
    ],
  };

  it('muestra filas antes y después, apartadas y particiones, sin relanzar', async () => {
    stubEventSource();
    stubApi({
      ...session(ALLOWED),
      [`GET /api/v1/runs/${APPLY_ID}`]: {
        body: {
          ...FINISHED, id: APPLY_ID, operation: 'bulk_apply', status: 'failed', my_role: 'owner',
          error_code: 'bulk_partial', error_message: 'Carga incompleta',
          params: { preview_run: PREVIEW_ID, confirm: 'destino' }, artifacts: [],
        },
      },
      [`GET /api/v1/runs/${APPLY_ID}/bulk-result`]: { body: RESULT },
    }); // prettier-ignore

    renderRoute(`/runs/${APPLY_ID}`);

    expect(await screen.findByText('Filas después')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    // Filas insertadas: lo que creció la tabla (12 − 10), no las 3 que util_bbdd cuenta como confirmadas (G37).
    expect(screen.getByText('Filas insertadas').nextElementSibling).toHaveTextContent('2');
    expect(screen.queryByText('Filas confirmadas')).not.toBeInTheDocument();
    expect(screen.queryByText('El recuento del destino no cuadra')).not.toBeInTheDocument();
    expect(screen.queryByText('No se cargó ninguna fila')).not.toBeInTheDocument();
    expect(screen.getByText('Hay filas apartadas')).toBeInTheDocument();
    expect(screen.getByRole('table', { name: 'Particiones' })).toHaveTextContent('duplicate key');
    expect(screen.getByRole('link', { name: 'Ver la vista previa' })).toHaveAttribute(
      'href',
      `/runs/${PREVIEW_ID}`,
    );
    expect(screen.queryByRole('button', { name: 'Relanzar' })).not.toBeInTheDocument();
  });

  it('avisa si el recuento del destino no cuadra con las filas confirmadas', async () => {
    stubEventSource();
    stubApi({
      ...session(ALLOWED),
      [`GET /api/v1/runs/${APPLY_ID}`]: {
        body: {
          ...FINISHED, id: APPLY_ID, operation: 'bulk_apply', status: 'succeeded', my_role: 'owner',
          params: { preview_run: PREVIEW_ID, confirm: 'destino' }, artifacts: [],
        },
      },
      [`GET /api/v1/runs/${APPLY_ID}/bulk-result`]: {
        body: { ...RESULT, rejected: 0, partitions: [], parallel: { workers: 1, reasons: [] }, target_rows_after: 11,
                verified: false },
      },
    }); // prettier-ignore

    renderRoute(`/runs/${APPLY_ID}`);

    expect(await screen.findByText('El recuento del destino no cuadra')).toBeInTheDocument();
    expect(screen.getByText(/confirmó 3 filas, pero la tabla creció en 1/)).toBeInTheDocument();
  });

  it('avisa si no se cargó ninguna fila porque todas se apartaron', async () => {
    stubEventSource();
    stubApi({
      ...session(ALLOWED),
      [`GET /api/v1/runs/${APPLY_ID}`]: {
        body: {
          ...FINISHED, id: APPLY_ID, operation: 'bulk_apply', status: 'succeeded', my_role: 'owner',
          params: { preview_run: PREVIEW_ID, confirm: 'destino' }, artifacts: [],
        },
      },
      // Caso real: 400 filas con la PK ya existente; util_bbdd las da por confirmadas y las aparta todas.
      [`GET /api/v1/runs/${APPLY_ID}/bulk-result`]: {
        body: { ...RESULT, rows: 400, committed: 400, matches: 400, rejected: 400, partitions: [],
                target_rows_before: 7386111, target_rows_after: 7386111 },
      },
    }); // prettier-ignore

    renderRoute(`/runs/${APPLY_ID}`);

    expect(await screen.findByText('No se cargó ninguna fila')).toBeInTheDocument();
    expect(screen.getByText(/Las 400 filas del fichero se apartaron en rechazos.csv/)).toBeInTheDocument();
    expect(screen.getByText('Filas insertadas').nextElementSibling).toHaveTextContent('0');
    expect(screen.queryByText('Hay filas apartadas')).not.toBeInTheDocument();
  });

  it('una carga cancelada dice si se deshizo entera o qué particiones quedan', async () => {
    stubEventSource();
    stubApi({
      ...session(ALLOWED),
      [`GET /api/v1/runs/${APPLY_ID}`]: {
        body: {
          ...FINISHED, id: APPLY_ID, operation: 'bulk_apply', status: 'cancelled', my_role: 'owner',
          params: { preview_run: PREVIEW_ID, confirm: 'destino' }, artifacts: [],
        },
      },
      [`GET /api/v1/runs/${APPLY_ID}/bulk-result`]: {
        body: { ...RESULT, rejected: 0, partitions: [], committed: 0, target_rows_after: 10, cancelled: true },
      },
    }); // prettier-ignore

    renderRoute(`/runs/${APPLY_ID}`);

    expect(await screen.findByText('Cancelada entre lotes')).toBeInTheDocument();
    expect(screen.getByText(/se deshizo entera/)).toBeInTheDocument();
  });

  it('una carga en curso se cancela entre lotes tras confirmarlo', async () => {
    stubEventSource();
    const running = {
      ...RUN, id: APPLY_ID, operation: 'bulk_apply', status: 'running', my_role: 'owner', artifacts: [],
      params: { preview_run: PREVIEW_ID, confirm: 'destino' },
    }; // prettier-ignore
    const fetchMock = stubApi({
      ...session(ALLOWED),
      [`GET /api/v1/runs/${APPLY_ID}`]: { body: running },
      [`POST /api/v1/runs/${APPLY_ID}/cancel`]: { status: 202, body: { ...running, cancel_requested: true } },
    });
    const user = userEvent.setup();

    renderRoute(`/runs/${APPLY_ID}`);

    await user.click(await screen.findByRole('button', { name: 'Cancelar' }));
    const dialog = await screen.findByRole('dialog', { name: 'Cancelar la carga' });
    expect(within(dialog).getByText(/se deshace entera/)).toBeInTheDocument();
    expect(callsTo(fetchMock, 'POST', `/api/v1/runs/${APPLY_ID}/cancel`)).toHaveLength(0);
    await user.click(within(dialog).getByRole('button', { name: 'Cancelar entre lotes' }));
    await waitFor(() =>
      expect(callsTo(fetchMock, 'POST', `/api/v1/runs/${APPLY_ID}/cancel`)).toHaveLength(1),
    );
  });
});
