import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi } from '../../test/api';
import { renderRoute } from '../../test/render';

const user = (id: number, username: string) => ({
  id,
  username,
  display_name: username.toUpperCase(),
  role: 'user',
  is_active: true,
  locked_until: null,
  created_at: '2026-11-06T08:00:00Z',
  last_login_at: null,
  can_run_sql: false,
  can_apply_ddl: false,
  can_write_data: false,
});

describe('listas con orden, paginación de 25 y búsqueda', () => {
  it('en el servidor: pide 25 filas y envía el orden y la búsqueda', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': { body: { items: [user(1, 'ana'), user(2, 'luis')], total: 60 } },
    });
    const ui = userEvent.setup();
    renderRoute('/admin/users');

    expect(await screen.findByText('1-25 de 60')).toBeInTheDocument();
    const params = () =>
      new URL(callsTo(fetchMock, 'GET', '/api/v1/users').at(-1)?.url ?? 'http://x').searchParams;
    expect(params().get('limit')).toBe('25');

    await ui.click(screen.getByRole('button', { name: 'Ordenar por Usuario' }));
    await waitFor(() => expect(params().get('sort')).toBe('username'));
    expect(params().get('order')).toBe('asc');
    await ui.click(screen.getByRole('button', { name: 'Ordenar por Usuario' }));
    await waitFor(() => expect(params().get('order')).toBe('desc'));

    await ui.click(screen.getByRole('button', { name: '3' }));
    await waitFor(() => expect(params().get('offset')).toBe('50'));
    await ui.type(screen.getByRole('textbox', { name: 'Buscar por usuario o nombre' }), 'lu');
    await waitFor(() => expect(params().get('q')).toBe('lu'));
    expect(params().get('offset')).toBe('0'); // la búsqueda vuelve a la página 1
  });

  it('en el cliente: ordena y busca sin pedir nada a la API', async () => {
    const entries = ['db.b.local', 'db.a.local', 'otro.example'].map((pattern, i) => ({
      id: i + 1,
      pattern,
      description: i === 2 ? 'externo' : '',
      created_at: `2026-11-0${i + 1}T08:00:00Z`,
    }));
    const fetchMock = stubApi({ ...session(ADMIN), 'GET /api/v1/admin/allowlist': { body: entries } });
    const ui = userEvent.setup();
    renderRoute('/admin/allowlist');

    const table = await screen.findByRole('table', { name: 'Destinos permitidos' });
    const first = () => within(table).getAllByRole('row')[1]?.textContent ?? '';
    expect(first()).toContain('db.a.local'); // orden inicial por patrón
    await ui.click(screen.getByRole('button', { name: 'Ordenar por Destino' }));
    expect(first()).toContain('otro.example');
    await ui.type(screen.getByRole('textbox', { name: 'Buscar por patrón o descripción' }), 'externo');
    expect(within(table).getAllByRole('row')).toHaveLength(2);
    expect(callsTo(fetchMock, 'GET', '/api/v1/admin/allowlist')).toHaveLength(1);
  });
});
