import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, USER, callsTo, session, stubApi } from '../../test/api';
import { renderRoute } from '../../test/render';

const RUN = {
  id: '01JRUN00000000000000000001',
  project_id: 5,
  project_name: 'Ventas',
  operation: 'documentation',
  status: 'succeeded',
  username: 'ana',
  created_at: '2026-11-06T08:00:00Z',
  finished_at: '2026-11-06T08:01:00Z',
  size_bytes: 2_097_152,
  artifacts_count: 12,
};
const PAGE = { items: [RUN, { ...RUN, id: '01JRUN00000000000000000002', status: 'running' }], total: 2 };

function routes() {
  return {
    ...session(ADMIN),
    'GET /api/v1/admin/runs': { body: PAGE },
    [`DELETE /api/v1/admin/runs/${RUN.id}`]: { status: 204 },
    'GET /api/v1/admin/projects/5/runs/summary': {
      body: { project_id: 5, project_name: 'Ventas', runs: 7, size_bytes: 10_485_760 },
    },
    'POST /api/v1/admin/projects/5/runs/delete': {
      body: { deleted: 5, skipped_active: 1, skipped_pending_dump: 1, freed_bytes: 8_388_608 },
    },
  };
}

describe('Administración → Ejecuciones', () => {
  it('lista las de todos los proyectos y ordena y busca en el servidor', async () => {
    const fetchMock = stubApi(routes());
    const user = userEvent.setup();

    renderRoute('/admin/runs');

    const table = await screen.findByRole('table', { name: 'Ejecuciones de todos los proyectos' });
    expect(within(table).getAllByText('Ventas')).toHaveLength(2);
    expect(within(table).getAllByText('2 MB').length).toBeGreaterThan(0);
    await user.click(screen.getByRole('button', { name: 'Ordenar por Tamaño' }));
    await waitFor(() =>
      expect(
        callsTo(fetchMock, 'GET', '/api/v1/admin/runs').some(
          (r) => new URL(r.url).searchParams.get('sort') === 'size',
        ),
      ).toBe(true),
    );
    await user.type(
      screen.getByRole('textbox', { name: 'Buscar por id, proyecto, operación o usuario' }),
      'vent',
    );
    await waitFor(() =>
      expect(
        callsTo(fetchMock, 'GET', '/api/v1/admin/runs').some(
          (r) => new URL(r.url).searchParams.get('q') === 'vent',
        ),
      ).toBe(true),
    );
    const last = callsTo(fetchMock, 'GET', '/api/v1/admin/runs').at(-1);
    expect(new URL(last?.url ?? 'http://x').searchParams.get('limit')).toBe('25');
  });

  it('elimina una ejecución solo tras escribir ELIMINAR', async () => {
    const fetchMock = stubApi(routes());
    const user = userEvent.setup();
    renderRoute('/admin/runs');

    await user.click(await screen.findByRole('button', { name: `Eliminar la ejecución ${RUN.id}` }));
    const dialog = await screen.findByRole('dialog', { name: 'Eliminar la ejecución' });
    expect(within(dialog).getByText('Espacio que se libera: 2 MB')).toBeInTheDocument();
    const confirm = within(dialog).getByRole('button', { name: 'Eliminar' });
    expect(confirm).toBeDisabled();
    await user.type(
      within(dialog).getByRole('textbox', { name: 'Escribe ELIMINAR para confirmar' }),
      'eliminar',
    );
    expect(confirm).toBeDisabled();
    await user.clear(within(dialog).getByRole('textbox', { name: 'Escribe ELIMINAR para confirmar' }));
    await user.type(
      within(dialog).getByRole('textbox', { name: 'Escribe ELIMINAR para confirmar' }),
      'ELIMINAR',
    );
    await user.click(confirm);

    await waitFor(() => expect(callsTo(fetchMock, 'DELETE', `/api/v1/admin/runs/${RUN.id}`)).toHaveLength(1));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('elimina las de un proyecto escribiendo su nombre y dice cuántas omitió', async () => {
    const fetchMock = stubApi(routes());
    const user = userEvent.setup();
    renderRoute('/admin/runs');

    const [first] = await screen.findAllByRole('button', {
      name: 'Eliminar todas las ejecuciones de Ventas',
    });
    if (!first) throw new Error('Sin botón');
    await user.click(first);
    const dialog = await screen.findByRole('dialog', { name: 'Eliminar las ejecuciones de «Ventas»' });
    expect(await within(dialog).findByText('El proyecto tiene 7 ejecuciones (10 MB).')).toBeInTheDocument();
    const confirm = within(dialog).getByRole('button', { name: 'Eliminar las ejecuciones' });
    expect(confirm).toBeDisabled();
    await user.type(
      within(dialog).getByRole('textbox', { name: /Escribe el nombre del proyecto/ }),
      'Ventas',
    );
    await user.click(confirm);

    expect(await within(dialog).findByText('5 ejecuciones eliminadas (8 MB liberados).')).toBeInTheDocument();
    expect(within(dialog).getByText('1 en cola o en curso: no se ha borrado.')).toBeInTheDocument();
    expect(
      within(dialog).getByText('1 volcado con constraints sin restaurar: no se ha borrado.'),
    ).toBeInTheDocument();
    expect(await callsTo(fetchMock, 'POST', '/api/v1/admin/projects/5/runs/delete')[0]?.json()).toEqual({
      confirm: 'Ventas',
    });
  });

  it('no aparece en el menú de un usuario sin rol de administrador', async () => {
    stubApi({ ...session(USER), 'GET /api/v1/projects': { body: { items: [], total: 0 } } });
    renderRoute('/projects');

    await screen.findByRole('link', { name: 'Proyectos' });
    expect(screen.queryByRole('link', { name: 'Ejecuciones de todos' })).not.toBeInTheDocument();
  });
});
