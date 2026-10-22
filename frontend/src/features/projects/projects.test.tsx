import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi } from '../../test/api';
import { CONNECTION } from '../../test/fixtures';
import { PROJECT } from '../../test/fixtures_runs';
import { renderRoute } from '../../test/render';

const DETAIL_ROUTES = {
  'GET /api/v1/projects/5': { body: PROJECT },
  'GET /api/v1/projects/5/runs': { body: { items: [], total: 0 } },
  'GET /api/v1/projects/5/connections': { body: [] },
};

describe('ProjectsPage', () => {
  it('lista mis proyectos con mi rol', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/projects': {
        body: { items: [PROJECT, { ...PROJECT, id: 6, name: 'Otro', my_role: 'viewer' }], total: 2 },
      },
    });

    renderRoute('/projects');

    const row = (await screen.findByRole('rowheader', { name: 'Otro' })).closest('tr') as HTMLElement;
    expect(within(row).getByText('Lector')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Migración 2026' })).toHaveAttribute('href', '/projects/5');
  });

  it('crea un proyecto y abre su detalle', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      ...DETAIL_ROUTES,
      'GET /api/v1/projects': { body: { items: [], total: 0 } },
      'POST /api/v1/projects': { status: 201, body: PROJECT },
    });
    const user = userEvent.setup();

    renderRoute('/projects');
    expect(await screen.findByText(/No participas en ningún proyecto/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Nuevo proyecto' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Crear proyecto' }));
    expect(within(dialog).getByText('Campo obligatorio')).toBeInTheDocument();
    await user.type(within(dialog).getByRole('textbox', { name: /^Nombre/ }), 'Migración 2026');
    await user.click(within(dialog).getByRole('button', { name: 'Crear proyecto' }));

    expect(await screen.findByRole('heading', { name: 'Migración 2026' })).toBeInTheDocument();
    expect(await callsTo(fetchMock, 'POST', '/api/v1/projects')[0]?.json()).toEqual({
      name: 'Migración 2026',
      description: '',
    });
  });
});

describe('ProjectDetailPage', () => {
  it('un lector no ve lanzar ni ajustes', async () => {
    stubApi({
      ...session(ADMIN),
      ...DETAIL_ROUTES,
      'GET /api/v1/projects/5': { body: { ...PROJECT, my_role: 'viewer' } },
    });

    renderRoute('/projects/5');

    expect(await screen.findByText(/no tiene ejecuciones/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Lanzar ejecución' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Ajustes' })).not.toBeInTheDocument();
  });

  it('el propietario ve lanzar y ajustes', async () => {
    stubApi({ ...session(ADMIN), ...DETAIL_ROUTES });

    renderRoute('/projects/5');

    expect(await screen.findByRole('button', { name: 'Lanzar ejecución' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Ajustes' })).toBeInTheDocument();
  });

  it('asocia una conexión con alias', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      ...DETAIL_ROUTES,
      'GET /api/v1/connections': { body: { items: [CONNECTION], total: 1 } },
      'POST /api/v1/projects/5/connections': {
        status: 201,
        body: {
          id: 1,
          alias: 'origen',
          connection_id: 7,
          connection_name: 'Ventas',
          db_type: 'postgresql',
          read_only: true,
          created_at: '2026-10-20T08:00:00Z',
        },
      },
    });
    const user = userEvent.setup();

    renderRoute('/projects/5?tab=connections');
    await screen.findByRole('option', { name: 'Ventas (postgresql)' });
    await user.selectOptions(
      await screen.findByRole('combobox', { name: 'Conexión' }),
      'Ventas (postgresql)',
    );
    await user.type(screen.getByRole('textbox', { name: /^Alias/ }), 'Origen');
    await user.click(screen.getByRole('button', { name: 'Asociar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/connections')).toHaveLength(1));
    expect(await callsTo(fetchMock, 'POST', '/api/v1/projects/5/connections')[0]?.json()).toEqual({
      connection_id: 7,
      alias: 'origen',
    });
  });

  it('añade un miembro con rol', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      ...DETAIL_ROUTES,
      'GET /api/v1/projects/5/members': {
        body: [
          {
            user_id: 1,
            username: 'admin',
            display_name: 'Admin',
            role: 'owner',
            added_at: '2026-10-20T08:00:00Z',
          },
        ],
      },
      'POST /api/v1/projects/5/members': {
        status: 201,
        body: {
          user_id: 2,
          username: 'ana',
          display_name: 'Ana',
          role: 'viewer',
          added_at: '2026-10-20T08:00:00Z',
        },
      },
    });
    const user = userEvent.setup();

    renderRoute('/projects/5?tab=members');
    expect(await screen.findByRole('button', { name: 'Salir del proyecto' })).toBeInTheDocument();
    await user.type(screen.getByRole('textbox', { name: 'Usuario' }), 'ana');
    await user.click(screen.getByRole('button', { name: 'Añadir miembro' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/members')).toHaveLength(1));
    expect(await callsTo(fetchMock, 'POST', '/api/v1/projects/5/members')[0]?.json()).toEqual({
      username: 'ana',
      role: 'viewer',
    });
  });

  it('un proyecto ajeno muestra el 404', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/projects/9': { status: 404, body: { title: 'Proyecto no encontrado', status: 404 } },
    });

    renderRoute('/projects/9');

    expect(await screen.findByRole('alert')).toHaveTextContent('Proyecto no encontrado');
  });
});
