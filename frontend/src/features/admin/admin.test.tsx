import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, ADMIN_ROLE, ALL_PERMISSIONS, callsTo, session, stubApi, USER_ROLE } from '../../test/api';
import { renderRoute } from '../../test/render';

const ANA = {
  id: 2,
  username: 'ana',
  display_name: 'Ana',
  role: USER_ROLE,
  permissions: [] as string[],
  is_active: true,
  locked_until: null,
  password_changed_at: '2026-10-20T08:00:00Z',
  created_at: '2026-10-20T08:00:00Z',
  updated_at: '2026-10-20T08:00:00Z',
  project_count: 0,
};
const ADMIN_USER = {
  ...ANA,
  id: 1,
  username: 'admin',
  display_name: 'Admin',
  role: ADMIN_ROLE,
  permissions: [...ALL_PERMISSIONS] as string[],
};
const SQL_ROLE = { id: 7, name: 'SQL y DDL', builtin: null, permissions: ['sql.run', 'ddl.apply'] };
const ROLES = [
  {
    ...ADMIN_ROLE,
    permissions: [...ALL_PERMISSIONS],
    user_count: 1,
    created_at: '2026-11-25T08:00:00Z',
    updated_at: '2026-11-25T08:00:00Z',
  },
  {
    ...USER_ROLE,
    permissions: [],
    user_count: 1,
    created_at: '2026-11-25T08:00:00Z',
    updated_at: '2026-11-25T08:00:00Z',
  },
  { ...SQL_ROLE, user_count: 0, created_at: '2026-11-25T08:00:00Z', updated_at: '2026-11-25T08:00:00Z' },
];

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
      role_id: null,
      is_active: true,
      storage_quota_mb: null,
    });
  });

  it('da de alta con rol, cuota propia e inactivo', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/roles': { body: ROLES },
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
    await user.click(within(dialog).getByRole('combobox', { name: 'Rol' }));
    // También están las opciones del filtro de la página: la del modal es la última que se monta.
    const options = await screen.findAllByRole('option', { name: 'SQL y DDL', hidden: true });
    await user.click(options.at(-1) as HTMLElement);
    await user.click(within(dialog).getByRole('switch', { name: /Usar la cuota global/ }));
    const quota = within(dialog).getByRole('textbox', { name: /Cuota propia/ });
    await user.clear(quota);
    await user.type(quota, '500');
    await user.click(within(dialog).getByRole('button', { name: 'Crear usuario' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/users')).toHaveLength(1));
    expect(await callsTo(fetchMock, 'POST', '/api/v1/users')[0]?.json()).toMatchObject({
      is_active: false,
      role_id: 7,
      storage_quota_mb: 500,
    });
  });

  it('filtra por rol y estado', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/roles': { body: ROLES },
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
      expect(params.get('role_id')).toBe('1');
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

  it('transfiere desde la ventana de borrado y después deja eliminar', async () => {
    let transferred = false;
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': (request: Request) =>
        new URL(request.url).searchParams.get('status') === 'active'
          ? {
              body: {
                items: [ANA, { ...ANA, id: 3, username: 'mar', display_name: 'Mar' }],
                total: 2,
                active_admins: 1,
              },
            }
          : { body: { items: [{ ...ANA, project_count: 1 }], total: 1, active_admins: 1 } },
      'GET /api/v1/users/2/deletion-check': () => ({
        body: transferred
          ? { can_delete: true, reasons: [], projects: [], created_projects: [], connections: [] }
          : {
              can_delete: false,
              reasons: ['member', 'creator'],
              projects: [{ id: 5, name: 'Ventas', role: 'owner' }],
              created_projects: [{ id: 5, name: 'Ventas', role: null }],
              connections: [],
            },
      }),
      'GET /api/v1/users/2/transfer-preview': (request: Request) => {
        expect(new URL(request.url).searchParams.get('target_user_id')).toBe('3');
        return {
          body: {
            can_transfer: true,
            reasons: [],
            created_projects: [{ id: 5, name: 'Ventas', new_name: 'Ventas (de ana)' }],
            owned_projects: [{ id: 5, name: 'Ventas', role: 'owner' }],
            other_memberships: [{ id: 8, name: 'Ajeno', role: 'viewer' }],
            connections: [],
            busy_projects: [],
          },
        };
      },
      'POST /api/v1/users/2/transfer': () => {
        transferred = true;
        return {
          body: {
            can_transfer: true,
            reasons: [],
            created_projects: [],
            owned_projects: [],
            other_memberships: [],
            connections: [],
            busy_projects: [],
          },
        };
      },
    });
    const user = userEvent.setup();

    renderRoute('/admin/users');
    await user.click(await screen.findByRole('button', { name: 'Eliminar ana' }));
    await user.click(
      await within(await screen.findByRole('dialog')).findByRole('button', { name: 'Transferir…' }),
    );
    const dialog = await screen.findByRole('dialog', { name: 'Transferir lo de ana' });
    await user.click(within(dialog).getByRole('combobox', { name: /Usuario que lo recibe/ }));
    await user.click(await screen.findByRole('option', { name: /mar/, hidden: true }));

    expect(await within(dialog).findByText('Ventas → Ventas (de ana)')).toBeInTheDocument();
    expect(within(dialog).getByText('Ajeno (Lector)')).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Transferir' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/users/2/transfer')).toHaveLength(1));
    expect(await callsTo(fetchMock, 'POST', '/api/v1/users/2/transfer')[0]?.json()).toEqual({
      target_user_id: 3,
      remove_memberships: true,
    });
    // De vuelta en la ventana de borrado, ya se puede eliminar.
    const back = await screen.findByRole('dialog', { name: 'Eliminar usuario ana' });
    expect(await within(back).findByRole('button', { name: 'Eliminar' })).toBeInTheDocument();
  });

  it('explica por qué no se puede transferir', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': {
        body: { items: [ANA, { ...ANA, id: 3, username: 'mar' }], total: 2, active_admins: 1 },
      },
      'GET /api/v1/users/2/deletion-check': {
        body: {
          can_delete: false,
          reasons: ['creator'],
          projects: [],
          created_projects: [{ id: 5, name: 'Ventas', role: null }],
          connections: [],
        },
      },
      'GET /api/v1/users/2/transfer-preview': {
        body: {
          can_transfer: false,
          reasons: ['busy'],
          created_projects: [{ id: 5, name: 'Ventas', new_name: null }],
          owned_projects: [],
          other_memberships: [],
          connections: [],
          busy_projects: [{ id: 5, name: 'Ventas' }],
        },
      },
    });
    const user = userEvent.setup();

    renderRoute('/admin/users');
    await user.click(await screen.findByRole('button', { name: 'Eliminar ana' }));
    await user.click(
      await within(await screen.findByRole('dialog')).findByRole('button', { name: 'Transferir…' }),
    );
    const dialog = await screen.findByRole('dialog', { name: 'Transferir lo de ana' });
    await user.click(within(dialog).getByRole('combobox', { name: /Usuario que lo recibe/ }));
    await user.click(await screen.findByRole('option', { name: /mar/, hidden: true }));

    expect(await within(dialog).findByText('No se puede transferir')).toBeInTheDocument();
    expect(within(dialog).getByText(/ejecuciones en cola o en curso/)).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: 'Transferir' })).toBeDisabled();
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
    // Detalles completos, un campo por línea.
    const line = (text: string) => (_: string, el: Element | null) =>
      el?.tagName === 'P' && el.textContent === text;
    expect(screen.getByText(line('username: nadie'))).toBeInTheDocument();
    expect(screen.getByText(line('reason: unknown_user'))).toBeInTheDocument();
    expect(screen.getByText('Fallido').closest('td')).toHaveStyle({ whiteSpace: 'nowrap' });

    await user.click(screen.getByRole('radio', { name: 'Autenticación' }));

    await waitFor(() => {
      const last = callsTo(fetchMock, 'GET', '/api/v1/audit').at(-1);
      expect(new URL(last?.url ?? '').searchParams.get('action')).toBe('auth.');
    });
  });
});
