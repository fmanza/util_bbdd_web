import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi } from '../../test/api';
import { stubEventSource } from '../../test/eventSource';
import { FINISHED, NOOP, PROJECT, RUN, RUN_DETAIL, RUN_ID } from '../../test/fixtures_runs';
import { renderRoute } from '../../test/render';

describe('lanzar una ejecución', () => {
  it('envía los parámetros tipados y abre el detalle', async () => {
    stubEventSource();
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/projects/5': { body: PROJECT },
      'GET /api/v1/projects/5/runs': { body: { items: [], total: 0 } },
      'GET /api/v1/projects/5/connections': { body: [] },
      'GET /api/v1/operations': { body: [NOOP] },
      'POST /api/v1/projects/5/runs': { status: 202, body: { ...RUN, status: 'queued' } },
      [`GET /api/v1/runs/${RUN_ID}`]: { body: { ...RUN_DETAIL, status: 'queued' } },
    });
    const user = userEvent.setup();

    renderRoute('/projects/5');
    await user.click(await screen.findByRole('button', { name: 'Lanzar ejecución' }));
    const dialog = await screen.findByRole('dialog');
    const steps = await within(dialog).findByRole('textbox', { name: 'Pasos' });
    await user.clear(steps);
    await user.type(steps, '99');
    await user.click(within(dialog).getByRole('button', { name: 'Lanzar' }));
    expect(await within(dialog).findByText('Entre 1 y 20')).toBeInTheDocument();
    expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')).toHaveLength(0);

    await user.clear(steps);
    await user.type(steps, '2');
    await user.click(within(dialog).getByRole('button', { name: 'Lanzar' }));

    expect(await screen.findByRole('heading', { name: 'Ejecución noop' })).toBeInTheDocument();
    expect(await callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')[0]?.json()).toEqual({
      operation: 'noop',
      params: { steps: 2, step_seconds: 1, fail: false, connection: null },
    });
  });
});

describe('RunDetailPage', () => {
  it('sigue el progreso por SSE y muestra los artefactos al terminar', async () => {
    const EventSourceMock = stubEventSource();
    let finished = false;
    stubApi({
      ...session(ADMIN),
      [`GET /api/v1/runs/${RUN_ID}`]: () => ({ body: finished ? FINISHED : RUN_DETAIL }),
      [`GET /api/v1/runs/${RUN_ID}/artifacts/12/preview`]: { text: 'SELECT 1 AS ok;' },
    });
    const user = userEvent.setup();

    renderRoute(`/runs/${RUN_ID}`);
    expect(await screen.findByText('Paso 1 de 2')).toBeInTheDocument();
    const source = EventSourceMock.instances.at(-1);
    expect(source?.url).toBe(`/api/v1/runs/${RUN_ID}/events`);

    source?.emit('run', { ...RUN, progress_message: 'Paso 2 de 2', progress_pct: 100 });
    expect(await screen.findByText('Paso 2 de 2')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'Progreso: 100 %' })).toBeInTheDocument();

    finished = true;
    source?.emit('end', { id: RUN_ID, status: 'succeeded' });
    expect(await screen.findByText('Correcta')).toBeInTheDocument();
    expect(source?.closed).toBe(true);

    const iframe = await screen.findByTitle('Vista previa de outputs/html/resumen.html');
    expect(iframe).toHaveAttribute('sandbox', '');
    expect(iframe).toHaveAttribute('src', `/api/v1/runs/${RUN_ID}/artifacts/11/preview`);
    expect(screen.getByRole('link', { name: 'Descargar ZIP' })).toHaveAttribute(
      'href',
      `/api/v1/runs/${RUN_ID}/archive`,
    );

    await user.click(screen.getByText('ejemplo.sql'));
    expect(await screen.findByText('SELECT 1 AS ok;')).toBeInTheDocument();
  });

  it('un evento run terminal recarga los artefactos aunque no llegue end', async () => {
    const EventSourceMock = stubEventSource();
    let finished = false;
    stubApi({
      ...session(ADMIN),
      [`GET /api/v1/runs/${RUN_ID}`]: () => ({ body: finished ? FINISHED : RUN_DETAIL }),
    });

    renderRoute(`/runs/${RUN_ID}`);
    await screen.findByText('Paso 1 de 2');
    finished = true;
    EventSourceMock.instances.at(-1)?.emit('run', { ...FINISHED, artifacts: undefined });

    expect(await screen.findByTitle('Vista previa de outputs/html/resumen.html')).toBeInTheDocument();
    expect(EventSourceMock.instances.at(-1)?.closed).toBe(true);
  });

  it('cancela una ejecución en curso', async () => {
    stubEventSource();
    const fetchMock = stubApi({
      ...session(ADMIN),
      [`GET /api/v1/runs/${RUN_ID}`]: { body: RUN_DETAIL },
      [`POST /api/v1/runs/${RUN_ID}/cancel`]: { status: 202, body: { ...RUN, cancel_requested: true } },
    });
    const user = userEvent.setup();

    renderRoute(`/runs/${RUN_ID}`);
    await user.click(await screen.findByRole('button', { name: 'Cancelar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', `/api/v1/runs/${RUN_ID}/cancel`)).toHaveLength(1));
  });

  it('si falla el SSE pasa a sondeo', async () => {
    const EventSourceMock = stubEventSource();
    stubApi({ ...session(ADMIN), [`GET /api/v1/runs/${RUN_ID}`]: { body: RUN_DETAIL } });

    renderRoute(`/runs/${RUN_ID}`);
    await screen.findByText('Paso 1 de 2');
    EventSourceMock.instances.at(-1)?.fail();

    expect(await screen.findByText(/Actualización cada 2 s/)).toBeInTheDocument();
  });

  it('un lector no puede cancelar ni purgar', async () => {
    stubEventSource();
    stubApi({
      ...session(ADMIN),
      [`GET /api/v1/runs/${RUN_ID}`]: { body: { ...FINISHED, my_role: 'viewer' } },
    });

    renderRoute(`/runs/${RUN_ID}`);

    expect(await screen.findByText('Correcta')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Purgar' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Relanzar' })).not.toBeInTheDocument();
  });
});

describe('RunsPage', () => {
  it('lista las ejecuciones de mis proyectos', async () => {
    stubApi({ ...session(ADMIN), 'GET /api/v1/runs': { body: { items: [{ ...FINISHED }], total: 1 } } });

    renderRoute('/runs');

    expect(await screen.findByRole('link', { name: 'Migración 2026' })).toHaveAttribute(
      'href',
      '/projects/5',
    );
    expect(screen.getByRole('link', { name: `Abrir la ejecución ${RUN_ID}` })).toHaveAttribute(
      'href',
      `/runs/${RUN_ID}`,
    );
    expect(screen.getByText('3 s')).toBeInTheDocument();
  });
});
