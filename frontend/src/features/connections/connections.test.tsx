import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi, USER } from '../../test/api';
import { CONNECTION, PG_ENGINE, SQLITE_ENGINE } from '../../test/fixtures';
import { renderRoute } from '../../test/render';

const ENGINES = { 'GET /api/v1/engines': { body: [PG_ENGINE, SQLITE_ENGINE] } };

describe('ConnectionsPage', () => {
  it('lista conexiones con destino, acceso y última prueba', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/connections': {
        body: {
          items: [
            CONNECTION,
            {
              ...CONNECTION,
              id: 8,
              name: 'Común',
              visibility: 'shared',
              editable: false,
              last_test_ok: false,
            },
          ],
          total: 2,
        },
      },
    });

    renderRoute('/connections');

    const row = (await screen.findByRole('rowheader', { name: 'Común' })).closest('tr') as HTMLElement;
    expect(within(row).getByText('Compartida')).toBeInTheDocument();
    expect(within(row).getByText('Fallida')).toBeInTheDocument();
    expect(screen.getAllByText('db.corp:5432/ventas')).toHaveLength(2);
    expect(screen.getByText('Sin probar')).toBeInTheDocument();
  });

  it('muestra el estado vacío', async () => {
    stubApi({ ...session(USER), 'GET /api/v1/connections': { body: { items: [], total: 0 } } });

    renderRoute('/connections');

    expect(await screen.findByText(/No hay conexiones/)).toBeInTheDocument();
  });
});

describe('formulario de conexión', () => {
  it('genera los campos del motor y valida con Zod sin llamar a la API', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      ...ENGINES,
      'GET /api/v1/engines/postgresql': { body: PG_ENGINE },
    });
    const user = userEvent.setup();

    renderRoute('/connections/new?db_type=postgresql');

    expect(await screen.findByRole('textbox', { name: /^host/ })).toBeInTheDocument();
    expect(screen.getByLabelText(/^Contraseña/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Opciones avanzadas (1)' })).toBeInTheDocument();
    expect(screen.queryByLabelText(/^Visibilidad/)).not.toBeInTheDocument();

    await user.type(screen.getByRole('textbox', { name: /^port/ }), 'abc');
    await user.click(screen.getByRole('button', { name: 'Crear conexión' }));

    expect(await screen.findByText('El nombre es obligatorio')).toBeInTheDocument();
    expect(screen.getByText('«host» es obligatorio')).toBeInTheDocument();
    expect(screen.getByText('La contraseña es obligatoria')).toBeInTheDocument();
    expect(screen.getByText('Debe ser un número entero')).toBeInTheDocument();
    expect(callsTo(fetchMock, 'POST', '/api/v1/connections')).toHaveLength(0);
  });

  it('envía params tipados y la contraseña aparte, y abre el detalle', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      ...ENGINES,
      'GET /api/v1/engines/postgresql': { body: PG_ENGINE },
      'POST /api/v1/connections': { status: 201, body: CONNECTION },
      'GET /api/v1/connections/7': { body: CONNECTION },
    });
    const user = userEvent.setup();

    renderRoute('/connections/new?db_type=postgresql');
    await user.type(await screen.findByRole('textbox', { name: /^Nombre/ }), 'Ventas');
    await user.type(screen.getByRole('textbox', { name: /^host/ }), 'db.corp');
    await user.type(screen.getByRole('textbox', { name: /^user/ }), 'lector');
    await user.type(screen.getByRole('textbox', { name: /^database/ }), 'ventas');
    await user.type(screen.getByRole('textbox', { name: /^port/ }), '5433');
    await user.type(screen.getByLabelText(/^Contraseña/), 'secreta');
    await user.click(screen.getByRole('button', { name: 'Crear conexión' }));

    expect(await screen.findByRole('heading', { name: 'Ventas' })).toBeInTheDocument();
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/connections');
    expect(await request?.json()).toEqual({
      name: 'Ventas',
      description: '',
      db_type: 'postgresql',
      params: { host: 'db.corp', user: 'lector', database: 'ventas', port: 5433 },
      password: 'secreta',
      read_only: true,
      visibility: 'private',
    });
  });

  it('SQLite no pide contraseña y explica la carpeta de ficheros', async () => {
    stubApi({ ...session(ADMIN), ...ENGINES, 'GET /api/v1/engines/sqlite': { body: SQLITE_ENGINE } });

    renderRoute('/connections/new?db_type=sqlite');

    expect(await screen.findByRole('textbox', { name: /^database/ })).toBeInTheDocument();
    expect(screen.queryByLabelText(/^Contraseña/)).not.toBeInTheDocument();
    expect(screen.getByText(/UBW_FILES_DIR/)).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: /^Visibilidad/ })).toBeInTheDocument();
  });

  it('muestra en el campo el error 422 del servidor', async () => {
    stubApi({
      ...session(USER),
      ...ENGINES,
      'GET /api/v1/engines/sqlite': { body: SQLITE_ENGINE },
      'POST /api/v1/connections': {
        status: 422,
        body: {
          title: 'Parámetros de conexión no válidos',
          status: 422,
          detail: 'Ruta fuera de UBW_FILES_DIR',
          errors: [
            { loc: ['body', 'params', 'database'], msg: 'Ruta fuera de la carpeta', type: 'value_error' },
          ],
        },
      },
    });
    const user = userEvent.setup();

    renderRoute('/connections/new?db_type=sqlite');
    await user.type(await screen.findByRole('textbox', { name: /^Nombre/ }), 'Local');
    await user.type(screen.getByRole('textbox', { name: /^database/ }), '../config.db');
    await user.click(screen.getByRole('button', { name: 'Crear conexión' }));

    expect(await screen.findByText('Ruta fuera de la carpeta')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Parámetros de conexión no válidos');
  });

  it('en edición conserva la contraseña si se deja vacía', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      'GET /api/v1/connections/7': { body: CONNECTION },
      'GET /api/v1/engines/postgresql': { body: PG_ENGINE },
      'PATCH /api/v1/connections/7': { body: CONNECTION },
    });
    const user = userEvent.setup();

    renderRoute('/connections/7/edit');
    const host = await screen.findByRole('textbox', { name: /^host/ });
    expect(host).toHaveValue('db.corp');
    expect(screen.getByText('Déjala vacía para conservar la guardada.')).toBeInTheDocument();
    await user.clear(host);
    await user.type(host, 'db2.corp');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'PATCH', '/api/v1/connections/7')).toHaveLength(1));
    const body = (await callsTo(fetchMock, 'PATCH', '/api/v1/connections/7')[0]?.json()) as Record<
      string,
      unknown
    >;
    expect(body.params).toEqual({ host: 'db2.corp', user: 'lector', database: 'ventas', port: 5432 });
    expect(body).not.toHaveProperty('password');
  });
});

describe('ConnectionDetailPage', () => {
  it('prueba la conexión y muestra la versión', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/connections/7': { body: CONNECTION },
      'POST /api/v1/connections/7/test': {
        body: {
          ok: true,
          duration_ms: 42,
          server_version: '17.2',
          tested_at: '2026-10-20T08:00:00Z',
          error: null,
        },
      },
    });
    const user = userEvent.setup();

    renderRoute('/connections/7');
    expect(await screen.findByText('Guardada (cifrada)')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Probar conexión' }));

    expect(await screen.findByText('Conexión correcta')).toBeInTheDocument();
    expect(screen.getByText('Versión del servidor 17.2 · 42 ms')).toBeInTheDocument();
  });

  it('muestra el mensaje saneado de un fallo y el readiness', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/connections/7': { body: CONNECTION },
      'POST /api/v1/connections/7/test': {
        body: {
          ok: false,
          duration_ms: 0,
          server_version: null,
          tested_at: '2026-10-20T08:00:00Z',
          error: { code: 'not_allowed', message: 'El destino no está en la lista de destinos permitidos.' },
        },
      },
      'GET /api/v1/connections/7/readiness': {
        body: {
          supported: true,
          dynamic: true,
          detail: null,
          checked_at: '2026-10-20T08:00:00Z',
          findings: [
            { level: 'WARNING', param: 'shared_buffers', current: '128MB', recommendation: 'Subir a 25 %' },
          ],
          error: null,
        },
      },
    });
    const user = userEvent.setup();

    renderRoute('/connections/7');
    await user.click(await screen.findByRole('button', { name: 'Probar conexión' }));
    expect(await screen.findByText('La conexión ha fallado')).toBeInTheDocument();
    expect(screen.getByText(/lista de destinos permitidos/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Readiness' }));
    expect(await screen.findByText('shared_buffers')).toBeInTheDocument();
    expect(screen.getByText('WARNING')).toBeInTheDocument();
  });

  it('borra tras confirmar repitiendo el nombre', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      'GET /api/v1/connections/7': { body: CONNECTION },
      'DELETE /api/v1/connections/7': { status: 204 },
      'GET /api/v1/connections': { body: { items: [], total: 0 } },
    });
    const user = userEvent.setup();

    renderRoute('/connections/7');
    await user.click(await screen.findByRole('button', { name: 'Borrar' }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent('Se borrará la conexión «Ventas»');
    await user.click(within(dialog).getByRole('button', { name: 'Borrar' }));

    expect(await screen.findByText(/No hay conexiones/)).toBeInTheDocument();
    expect(callsTo(fetchMock, 'DELETE', '/api/v1/connections/7')).toHaveLength(1);
  });

  it('una compartida ajena no ofrece editar ni borrar', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/connections/7': { body: { ...CONNECTION, visibility: 'shared', editable: false } },
    });

    renderRoute('/connections/7');

    expect(await screen.findByRole('button', { name: 'Probar conexión' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Editar' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Borrar' })).not.toBeInTheDocument();
  });

  it('una conexión no visible muestra el 404', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/connections/99': { status: 404, body: { title: 'Conexión no encontrada', status: 404 } },
    });

    renderRoute('/connections/99');

    expect(await screen.findByRole('alert')).toHaveTextContent('Conexión no encontrada');
  });
});
