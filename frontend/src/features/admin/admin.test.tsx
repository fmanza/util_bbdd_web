import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi } from '../../test/api';
import { renderRoute } from '../../test/render';

const ANA = {
  id: 2,
  username: 'ana',
  display_name: 'Ana',
  role: 'user',
  is_active: true,
  can_run_sql: false,
  can_apply_ddl: false,
  locked_until: null,
  password_changed_at: '2026-10-20T08:00:00Z',
  created_at: '2026-10-20T08:00:00Z',
  updated_at: '2026-10-20T08:00:00Z',
};

describe('UsersPage', () => {
  it('lista usuarios con su estado', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': {
        body: { items: [ANA, { ...ANA, id: 3, username: 'luis', is_active: false }], total: 2 },
      },
    });

    renderRoute('/admin/users');

    expect(await screen.findByText('ana')).toBeInTheDocument();
    expect(screen.getByText('Desactivado')).toBeInTheDocument();
    expect(screen.getByText('Activo')).toBeInTheDocument();
  });

  it('muestra el estado vacío', async () => {
    stubApi({ ...session(ADMIN), 'GET /api/v1/users': { body: { items: [], total: 0 } } });

    renderRoute('/admin/users');

    expect(await screen.findByText('No hay usuarios que coincidan.')).toBeInTheDocument();
  });

  it('muestra el error de la API', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': { status: 500, body: { title: 'Error interno', status: 500 } },
    });

    renderRoute('/admin/users');

    expect(await screen.findByRole('alert')).toHaveTextContent('Error interno');
  });

  it('crea un usuario y valida el formulario', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': { body: { items: [], total: 0 } },
      'POST /api/v1/users': { status: 201, body: { ...ANA, id: 9, username: 'luis' } },
    });
    const user = userEvent.setup();

    renderRoute('/admin/users');
    await user.click(await screen.findByRole('button', { name: 'Nuevo usuario' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Crear usuario' }));
    expect(within(dialog).getByText('Debe tener al menos 12 caracteres')).toBeInTheDocument();
    expect(callsTo(fetchMock, 'POST', '/api/v1/users')).toHaveLength(0);

    await user.type(within(dialog).getByRole('textbox', { name: /^Usuario/ }), 'luis');
    await user.type(within(dialog).getByRole('textbox', { name: /Nombre visible/ }), 'Luis');
    await user.type(within(dialog).getByLabelText(/^Contraseña/), 'frase-de-paso-luis');
    await user.click(within(dialog).getByRole('button', { name: 'Crear usuario' }));

    await screen.findByRole('button', { name: 'Nuevo usuario' });
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/users');
    expect(await request?.json()).toEqual({
      username: 'luis',
      display_name: 'Luis',
      password: 'frase-de-paso-luis',
      role: 'user',
    });
  });

  it('desactiva un usuario enviando solo el cambio', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': { body: { items: [ANA], total: 1 } },
      'PATCH /api/v1/users/2': { body: { ...ANA, is_active: false } },
    });
    const user = userEvent.setup();

    renderRoute('/admin/users');
    await user.click(await screen.findByRole('button', { name: 'Editar ana' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('switch', { name: /Cuenta activa/ }));
    await user.click(within(dialog).getByRole('button', { name: 'Guardar' }));

    await screen.findByRole('button', { name: 'Nuevo usuario' });
    const [request] = callsTo(fetchMock, 'PATCH', '/api/v1/users/2');
    expect(await request?.json()).toEqual({ is_active: false });
  });
});

describe('SessionsPage', () => {
  it('revoca una sesión tras confirmar', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/sessions': {
        body: {
          items: [
            {
              id: 7,
              user_id: 2,
              username: 'ana',
              created_at: '2026-10-20T08:00:00Z',
              last_seen_at: '2026-10-20T08:05:00Z',
              expires_at: '2026-10-20T20:00:00Z',
              ip: '10.0.0.5',
              user_agent: 'Firefox',
              current: false,
            },
          ],
          total: 1,
        },
      },
      'DELETE /api/v1/sessions/7': { status: 204 },
    });
    const user = userEvent.setup();

    renderRoute('/admin/sessions');
    await user.click(await screen.findByRole('button', { name: 'Revocar sesión de ana' }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent('Se cerrará la sesión de ana desde 10.0.0.5.');
    await user.click(within(dialog).getByRole('button', { name: 'Revocar' }));

    await screen.findByText('Sesiones activas');
    expect(callsTo(fetchMock, 'DELETE', '/api/v1/sessions/7')).toHaveLength(1);
  });
});

describe('AuditPage', () => {
  it('muestra eventos traducidos y filtra por tipo', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/audit': {
        body: {
          items: [
            {
              id: 1,
              ts: '2026-10-20T08:00:00Z',
              actor_user_id: null,
              actor_username: null,
              action: 'auth.login',
              outcome: 'failure',
              target_type: null,
              target_id: null,
              ip: '10.0.0.9',
              details: { username: 'nadie', reason: 'unknown_user' },
            },
          ],
          total: 1,
        },
      },
    });
    const user = userEvent.setup();

    renderRoute('/admin/audit');

    expect(await screen.findByText('Inicio de sesión')).toBeInTheDocument();
    expect(screen.getByText('Fallido')).toBeInTheDocument();
    expect(screen.getByText('Sistema')).toBeInTheDocument();

    await user.click(screen.getByRole('radio', { name: 'Autenticación' }));

    await waitFor(() => {
      const last = callsTo(fetchMock, 'GET', '/api/v1/audit').at(-1);
      expect(new URL(last?.url ?? '').searchParams.get('action')).toBe('auth.');
    });
  });
});
