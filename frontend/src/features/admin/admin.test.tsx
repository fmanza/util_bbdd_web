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
  can_write_data: false,
  locked_until: null,
  password_changed_at: '2026-10-20T08:00:00Z',
  created_at: '2026-10-20T08:00:00Z',
  updated_at: '2026-10-20T08:00:00Z',
  project_count: 0,
};
const ADMIN_USER = { ...ANA, id: 1, username: 'admin', display_name: 'Admin', role: 'admin' };

describe('UsersPage', () => {
  it('lista usuarios con su estado', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': {
        body: {
          items: [ANA, { ...ANA, id: 3, username: 'luis', is_active: false }],
          total: 2,
          active_admins: 1,
        },
      },
    });

    renderRoute('/admin/users');

    expect(await screen.findByText('ana')).toBeInTheDocument();
    const table = screen.getByRole('table');
    expect(within(table).getByText('Desactivado')).toBeInTheDocument();
    expect(within(table).getByText('Activo')).toBeInTheDocument();
  });

  it('muestra el estado vacío', async () => {
    stubApi({ ...session(ADMIN), 'GET /api/v1/users': { body: { items: [], total: 0, active_admins: 1 } } });

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
      'GET /api/v1/users': { body: { items: [], total: 0, active_admins: 1 } },
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
      is_active: true,
      can_run_sql: false,
      can_apply_ddl: false,
      can_write_data: false,
      storage_quota_mb: null,
    });
  });

  it('da de alta con permisos, cuota propia e inactivo', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': { body: { items: [], total: 0, active_admins: 1 } },
      'POST /api/v1/users': { status: 201, body: { ...ANA, id: 9, username: 'luis' } },
    });
    const user = userEvent.setup();

    renderRoute('/admin/users');
    await user.click(await screen.findByRole('button', { name: 'Nuevo usuario' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: /^Usuario/ }), 'luis');
    await user.type(within(dialog).getByRole('textbox', { name: /Nombre visible/ }), 'Luis');
    await user.type(within(dialog).getByLabelText(/^Contraseña/), 'frase-de-paso-luis');
    await user.click(within(dialog).getByRole('switch', { name: /Cuenta activa/ }));
    await user.click(within(dialog).getByRole('switch', { name: /Puede ejecutar SQL libre/ }));
    await user.click(within(dialog).getByRole('switch', { name: /Puede aplicar DDL/ }));
    await user.click(within(dialog).getByRole('switch', { name: /Usar la cuota global/ }));
    const quota = within(dialog).getByRole('textbox', { name: /Cuota propia/ });
    await user.clear(quota);
    await user.type(quota, '500');
    await user.click(within(dialog).getByRole('button', { name: 'Crear usuario' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/users')).toHaveLength(1));
    expect(await callsTo(fetchMock, 'POST', '/api/v1/users')[0]?.json()).toMatchObject({
      is_active: false,
      can_run_sql: true,
      can_apply_ddl: true,
      can_write_data: false,
      storage_quota_mb: 500,
    });
  });

  it('filtra por rol y estado', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': { body: { items: [ANA], total: 1, active_admins: 1 } },
    });
    const user = userEvent.setup();

    renderRoute('/admin/users');
    await screen.findByText('ana');
    await user.click(screen.getByRole('combobox', { name: 'Rol' }));
    await user.click(await screen.findByRole('option', { name: 'Administrador', hidden: true }));
    await user.click(screen.getByRole('combobox', { name: 'Estado' }));
    await user.click(await screen.findByRole('option', { name: 'Bloqueado', hidden: true }));

    await waitFor(() => {
      const last = callsTo(fetchMock, 'GET', '/api/v1/users').at(-1);
      const params = new URL(last?.url ?? 'http://x').searchParams;
      expect(params.get('role')).toBe('admin');
      expect(params.get('status')).toBe('locked');
      expect(params.get('offset')).toBe('0');
    });
  });

  it('marca al único administrador: sin borrar y sin cambiar rol ni estado', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': { body: { items: [ADMIN_USER, ANA], total: 2, active_admins: 1 } },
    });
    const user = userEvent.setup();

    renderRoute('/admin/users');
    expect(await screen.findByText('Único administrador')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Eliminar admin' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Eliminar ana' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Editar admin' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByRole('switch', { name: /Cuenta activa/ })).toBeDisabled();
    expect(within(dialog).getByRole('combobox', { name: 'Rol' })).toBeDisabled();
  });

  it('desbloquea un usuario bloqueado', async () => {
    const locked = { ...ANA, locked_until: '2999-01-01T00:00:00Z' };
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': { body: { items: [locked], total: 1, active_admins: 1 } },
      'POST /api/v1/users/2/unlock': { body: ANA },
    });
    const user = userEvent.setup();

    renderRoute('/admin/users');
    expect(within(await screen.findByRole('table')).getByText('Bloqueado')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Desbloquear ana' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/users/2/unlock')).toHaveLength(1));
  });

  it('no deja borrar un usuario con proyectos y los muestra', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': { body: { items: [{ ...ANA, project_count: 1 }], total: 1, active_admins: 1 } },
      'GET /api/v1/users/2/deletion-check': {
        body: {
          can_delete: false,
          reasons: ['member', 'creator'],
          projects: [{ id: 5, name: 'Ventas 2026', role: 'editor' }],
          created_projects: [{ id: 6, name: 'Pruebas', role: null }],
          connections: [],
        },
      },
    });
    const user = userEvent.setup();

    renderRoute('/admin/users');
    await user.click(await screen.findByRole('button', { name: 'Eliminar ana' }));
    const dialog = await screen.findByRole('dialog');

    expect(await within(dialog).findByText('No se puede eliminar ana')).toBeInTheDocument();
    expect(within(dialog).getByText('Ventas 2026 (Editor)')).toBeInTheDocument();
    expect(within(dialog).getByText('Pruebas')).toBeInTheDocument();
    expect(within(dialog).getByText('Es miembro de proyectos.')).toBeInTheDocument();
    expect(within(dialog).queryByRole('button', { name: 'Eliminar' })).not.toBeInTheDocument();
    expect(callsTo(fetchMock, 'DELETE', '/api/v1/users/2')).toHaveLength(0);
  });

  it('borra un usuario sin dependencias tras confirmar', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': { body: { items: [ANA], total: 1, active_admins: 1 } },
      'GET /api/v1/users/2/deletion-check': {
        body: { can_delete: true, reasons: [], projects: [], created_projects: [], connections: [] },
      },
      'DELETE /api/v1/users/2': { status: 204 },
    });
    const user = userEvent.setup();

    renderRoute('/admin/users');
    await user.click(await screen.findByRole('button', { name: 'Eliminar ana' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(await within(dialog).findByRole('button', { name: 'Eliminar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'DELETE', '/api/v1/users/2')).toHaveLength(1));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    // Recargar la lista no repite la comprobación del usuario ya borrado (daría 404).
    expect(callsTo(fetchMock, 'GET', '/api/v1/users/2/deletion-check')).toHaveLength(1);
  });

  it('no ofrece eliminar la propia cuenta aunque haya más administradores', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': {
        body: { items: [ADMIN_USER, { ...ADMIN_USER, id: 7, username: 'jefa' }], total: 2, active_admins: 2 },
      },
    });

    renderRoute('/admin/users');

    expect(await screen.findByRole('button', { name: 'Eliminar jefa' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Eliminar admin' })).not.toBeInTheDocument();
    expect(screen.queryByText('Único administrador')).not.toBeInTheDocument();
  });

  it('desactiva un usuario enviando solo el cambio', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': { body: { items: [ANA], total: 1, active_admins: 1 } },
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
