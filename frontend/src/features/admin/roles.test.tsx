import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import {
  ADMIN,
  ADMIN_ROLE,
  ALL_PERMISSIONS,
  callsTo,
  PERMISSION_CATALOG,
  session,
  stubApi,
  USER,
  USER_ROLE,
  without,
} from '../../test/api';
import { renderRoute } from '../../test/render';

const STAMP = { created_at: '2026-11-25T08:00:00Z', updated_at: '2026-11-25T08:00:00Z' };
const ROLES = [
  { ...ADMIN_ROLE, permissions: [...ALL_PERMISSIONS], user_count: 1, ...STAMP },
  { ...USER_ROLE, permissions: [], user_count: 3, ...STAMP },
  { id: 7, name: 'Auditores', builtin: null, permissions: ['audit.read'], user_count: 0, ...STAMP },
  { id: 8, name: 'Migradores', builtin: null, permissions: ['ddl.apply'], user_count: 2, ...STAMP },
];
const routes = (me: object) => ({
  ...session(me),
  'GET /api/v1/roles': { body: ROLES },
  'GET /api/v1/roles/permissions': { body: PERMISSION_CATALOG },
});

describe('RolesPage', () => {
  it('lista los roles: los base traducidos y sin borrar, y no se borra uno con usuarios', async () => {
    stubApi(routes(ADMIN));

    renderRoute('/admin/roles');

    const table = await screen.findByRole('table');
    expect(within(table).getByText('Administrador')).toBeInTheDocument();
    expect(within(table).getAllByText('Base')).toHaveLength(2);
    expect(within(table).getAllByText('Ver la auditoría')).toHaveLength(2);
    expect(screen.queryByRole('button', { name: 'Borrar el rol Administrador' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Borrar el rol Migradores' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Borrar el rol Auditores' })).toBeEnabled();
  });

  it('crea un rol solo con permisos que se tienen, en el orden del catálogo', async () => {
    const fetchMock = stubApi({
      ...routes(without(ADMIN, 'data.write')),
      'POST /api/v1/roles': { status: 201, body: { ...ROLES[2], id: 9 } },
    });
    const user = userEvent.setup();

    renderRoute('/admin/roles');
    await user.click(await screen.findByRole('button', { name: 'Nuevo rol' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByRole('checkbox', { name: 'Escribir datos' })).toBeDisabled();
    await user.type(within(dialog).getByRole('textbox', { name: /Nombre/ }), 'Lectores');
    await user.click(within(dialog).getByRole('checkbox', { name: 'Ejecutar SQL libre' }));
    await user.click(within(dialog).getByRole('checkbox', { name: 'Ver la auditoría' }));
    await user.click(within(dialog).getByRole('button', { name: 'Guardar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/roles')).toHaveLength(1));
    expect(await callsTo(fetchMock, 'POST', '/api/v1/roles')[0]?.json()).toEqual({
      name: 'Lectores',
      permissions: ['audit.read', 'sql.run'],
    });
  }, 15_000);

  it('agrupa los permisos como el menú y «Todos» solo marca los que se tienen', async () => {
    const fetchMock = stubApi({
      ...routes(without(ADMIN, 'data.write')),
      'POST /api/v1/roles': { status: 201, body: { ...ROLES[2], id: 9 } },
    });
    const user = userEvent.setup();

    renderRoute('/admin/roles');
    await user.click(await screen.findByRole('button', { name: 'Nuevo rol' }));
    const dialog = await screen.findByRole('dialog');
    // «Todos» más los permisos de cada grupo.
    const boxes = (group: string) =>
      within(within(dialog).getByRole('group', { name: group })).getAllByRole('checkbox');
    expect(boxes('Acceso y seguridad')).toHaveLength(6);
    expect(
      within(within(dialog).getByRole('group', { name: 'Contenido compartido' })).getByRole('checkbox', {
        name: 'Gestionar plantillas globales',
      }),
    ).toBeInTheDocument();
    expect(
      within(within(dialog).getByRole('group', { name: 'Operación' })).getByRole('checkbox', {
        name: 'Administrar ejecuciones',
      }),
    ).toBeInTheDocument();
    expect(boxes('Conexiones y bases de datos')).toHaveLength(5);

    await user.type(within(dialog).getByRole('textbox', { name: /Nombre/ }), 'Datos');
    await user.click(
      within(dialog).getByRole('checkbox', { name: 'Todos los permisos de «Conexiones y bases de datos»' }),
    );
    expect(within(dialog).getByRole('checkbox', { name: 'Escribir datos' })).not.toBeChecked();
    await user.click(within(dialog).getByRole('button', { name: 'Guardar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/roles')).toHaveLength(1));
    expect(await callsTo(fetchMock, 'POST', '/api/v1/roles')[0]?.json()).toEqual({
      name: 'Datos',
      permissions: ['connections.share', 'sql.run', 'ddl.apply'],
    });
  }, 15_000);

  it('un rol base se ve sin poder cambiarlo', async () => {
    stubApi(routes(ADMIN));
    const user = userEvent.setup();

    renderRoute('/admin/roles');
    await user.click(await screen.findByRole('button', { name: 'Editar el rol Usuario' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Es un rol base: no se puede cambiar ni borrar.')).toBeInTheDocument();
    expect(within(dialog).getByRole('checkbox', { name: 'Gestionar usuarios' })).toBeDisabled();
    expect(within(dialog).queryByRole('button', { name: 'Guardar' })).not.toBeInTheDocument();
  });
});

describe('administración según los permisos del rol', () => {
  it('el menú muestra solo lo que permite el rol y las demás rutas dicen «sin permiso»', async () => {
    const auditor = {
      ...USER,
      role: { id: 7, name: 'Auditores', builtin: null },
      permissions: ['audit.read'],
    };
    stubApi({
      ...session(auditor),
      'GET /api/v1/users': { body: { items: [], total: 0, active_admins: 1 } },
    });

    renderRoute('/admin/users');

    expect(await screen.findByText('Sin permiso')).toBeInTheDocument();
    const nav = screen.getByRole('navigation');
    expect(within(nav).getByRole('link', { name: 'Auditoría' })).toBeInTheDocument();
    expect(within(nav).queryByRole('link', { name: 'Usuarios' })).not.toBeInTheDocument();
    expect(within(nav).queryByRole('link', { name: 'Roles' })).not.toBeInTheDocument();
  });

  it('un usuario sin permisos de administración no ve la sección', async () => {
    stubApi(session(USER));

    renderRoute('/');

    const nav = await screen.findByRole('navigation');
    await within(nav).findByRole('link', { name: 'Proyectos' });
    expect(within(nav).queryByText('Administración')).not.toBeInTheDocument();
  });
});
