import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi } from '../../test/api';
import { PROJECT, RUN } from '../../test/fixtures_runs';
import { renderRoute } from '../../test/render';
import type { Upload, UploadInfo } from './useBulk';

const UPLOAD: Upload = {
  id: '01JUPLOADUPLOADUPLOADUPLOA',
  filename: 'clientes.csv',
  kind: 'csv',
  size_bytes: 2048,
  sha256: 'a'.repeat(64),
  created_at: '2026-10-23T08:00:00Z',
  username: 'admin',
};

const INFO: UploadInfo = {
  columns: ['ID', 'nombre', 'notas'],
  sample: [['1', 'Ana', null]],
  delimiter: ';',
  encoding: 'utf-8',
  sheets: null,
};

const CONNECTIONS = [
  { id: 2, alias: 'destino', connection_id: 2, connection_name: 'Destino', db_type: 'postgresql', read_only: false,
    created_at: '2026-10-20T08:00:00Z' },
]; // prettier-ignore

const COLUMNS = ['id', 'nombre', 'alta'].map((name, ordinal) => ({
  name,
  ordinal,
  data_type: 'TEXT',
  nullable: true,
}));

const TREE = {
  engine: 'postgresql',
  schema_name: 'public',
  database: null,
  fetched_at: '2026-10-30T08:00:00Z',
  size_bytes: 1024,
  tables: [{ name: 'clientes', comment: null, columns: 3 }],
  views: [{ name: 'v_clientes', comment: null, materialized: false }],
  routines: [],
};

/** Rutas comunes de la pestaña, para combinarlas con las del catálogo de cada test. */
function stubRoutes() {
  return Object.entries({
    ...session(ADMIN),
    'GET /api/v1/projects/5': { body: PROJECT },
    'GET /api/v1/projects/5/runs': { body: { items: [], total: 0 } },
    'GET /api/v1/projects/5/connections': { body: CONNECTIONS },
    'GET /api/v1/projects/5/uploads': { body: [UPLOAD] },
    [`GET /api/v1/projects/5/uploads/${UPLOAD.id}/info`]: { body: INFO },
    'GET /api/v1/connections/2/metadata/schemas/public/tables/clientes': {
      body: { name: 'clientes', columns: COLUMNS },
    },
    'POST /api/v1/projects/5/runs': { status: 202, body: { ...RUN, id: '01JNEWNEWNEWNEWNEWNEWNEWNE' } },
  });
}

function stubTab(initial: Upload[] = [UPLOAD]) {
  let uploads = initial;
  return stubApi({
    ...session(ADMIN),
    'GET /api/v1/projects/5': { body: PROJECT },
    'GET /api/v1/projects/5/runs': { body: { items: [], total: 0 } },
    'GET /api/v1/projects/5/connections': { body: CONNECTIONS },
    'GET /api/v1/projects/5/uploads': () => ({ body: uploads }),
    'POST /api/v1/projects/5/uploads': () => {
      uploads = [UPLOAD];
      return { status: 201, body: UPLOAD };
    },
    [`DELETE /api/v1/projects/5/uploads/${UPLOAD.id}`]: { status: 204 },
    [`GET /api/v1/projects/5/uploads/${UPLOAD.id}/info`]: { body: INFO },
    'GET /api/v1/connections/2/metadata/schemas/public/tables/clientes': {
      body: { name: 'clientes', columns: COLUMNS },
    },
    'POST /api/v1/projects/5/runs': { status: 202, body: { ...RUN, id: '01JNEWNEWNEWNEWNEWNEWNEWNE' } },
  });
}

async function openTab(user: ReturnType<typeof userEvent.setup>) {
  renderRoute('/projects/5');
  await user.click(await screen.findByRole('tab', { name: 'Carga' }));
}

describe('pestaña Carga', () => {
  it('sube un fichero como multipart y lo deja elegido', async () => {
    const fetchMock = stubTab([]);
    const user = userEvent.setup();

    await openTab(user);
    expect(await screen.findByText('Todavía no hay ficheros en este proyecto.')).toBeInTheDocument();
    const input = document.querySelector<HTMLInputElement>('input[type="file"]');
    await user.upload(input as HTMLInputElement, new File(['ID;nombre\n1;Ana\n'], 'clientes.csv'));
    await user.click(screen.getByRole('button', { name: 'Subir' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/uploads')).toHaveLength(1));
    const request = callsTo(fetchMock, 'POST', '/api/v1/projects/5/uploads')[0] as Request;
    expect(request.headers.get('Content-Type')).toMatch(/^multipart\/form-data/);
    expect(await screen.findByRole('combobox', { name: 'Fichero' })).toHaveValue(UPLOAD.id);
  });

  it('borra un fichero', async () => {
    const fetchMock = stubTab();
    const user = userEvent.setup();

    await openTab(user);
    await user.click(await screen.findByRole('button', { name: 'Borrar clientes.csv' }));
    await waitFor(() =>
      expect(callsTo(fetchMock, 'DELETE', `/api/v1/projects/5/uploads/${UPLOAD.id}`)).toHaveLength(1),
    );
  });

  it('propone el mapeo por nombre y lanza la vista previa', async () => {
    const fetchMock = stubTab();
    const user = userEvent.setup();

    await openTab(user);
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Fichero' }), UPLOAD.id);
    await user.selectOptions(screen.getByRole('combobox', { name: 'Operación' }), 'update');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Conexión destino' }), 'destino');
    await user.type(screen.getByRole('combobox', { name: /Schema destino/ }), 'public');
    await user.type(screen.getByRole('combobox', { name: 'Tabla destino' }), 'clientes');

    // Con las columnas de la tabla, el mapeo se ofrece como desplegables con la propuesta por nombre.
    const idTarget = await screen.findByRole('combobox', { name: 'Columna de la tabla para «ID»' });
    expect(idTarget).toHaveValue('id');
    expect(screen.getByRole('combobox', { name: 'Columna de la tabla para «notas»' })).toHaveValue('');
    expect(screen.getByText('Separador')).toBeInTheDocument();
    await user.selectOptions(screen.getByRole('combobox', { name: 'Columna de la tabla para «nombre»' }), '');
    await user.click(screen.getByRole('button', { name: 'Vista previa' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')).toHaveLength(1));
    expect(await callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')[0]?.json()).toEqual({
      operation: 'bulk_preview',
      params: {
        upload: UPLOAD.id,
        target_connection: 'destino',
        target_schema: 'public',
        table: 'clientes',
        operation: 'update',
        mapping: { ID: 'id' },
        on_error: 'raise',
        parallel: false,
      },
    });
  });

  it('ofrece los schemas y las tablas de la conexión destino', async () => {
    const fetchMock = stubApi({
      ...Object.fromEntries(stubRoutes()),
      'GET /api/v1/connections/2/metadata/schemas': {
        body: {
          default: 'public',
          schemas: [
            { name: 'public', system: false, cached: true },
            { name: 'ventas', system: false, cached: false },
            { name: 'pg_catalog', system: true, cached: false },
          ],
        },
      },
      'GET /api/v1/connections/2/metadata/schemas/public': { body: TREE },
    });
    const user = userEvent.setup();

    await openTab(user);
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Fichero' }), UPLOAD.id);
    await user.selectOptions(screen.getByRole('combobox', { name: 'Conexión destino' }), 'destino');

    const schema = screen.getByRole('combobox', { name: /Schema destino/ });
    await waitFor(() => expect(schema).toHaveAttribute('placeholder', 'public'));
    // jsdom no posiciona el desplegable de Mantine (queda con display: none): opciones con `hidden`, elección
    // con el teclado.
    await user.click(schema);
    expect(await screen.findByRole('option', { name: 'ventas', hidden: true })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'pg_catalog', hidden: true })).not.toBeInTheDocument();
    await user.keyboard('{Escape}');

    // Sin schema elegido, las tablas son las del schema de la conexión; las vistas no se ofrecen.
    const table = screen.getByRole('combobox', { name: 'Tabla destino' });
    await user.click(table);
    expect(await screen.findByRole('option', { name: 'clientes', hidden: true })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'v_clientes', hidden: true })).not.toBeInTheDocument();
    await user.keyboard('{ArrowDown}{Enter}');
    expect(table).toHaveValue('clientes');
    expect(await screen.findByRole('combobox', { name: 'Columna de la tabla para «ID»' })).toHaveValue('id');

    await user.click(screen.getByRole('button', { name: 'Vista previa' }));
    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')).toHaveLength(1));
    const body = (await callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')[0]?.json()) as {
      params: Record<string, unknown>;
    };
    expect(body.params).toMatchObject({ target_connection: 'destino', table: 'clientes' });
    expect(body.params).not.toHaveProperty('target_schema');
  });

  it('si el catálogo no se puede leer, el schema y la tabla se escriben a mano', async () => {
    stubApi({
      ...Object.fromEntries(stubRoutes()),
      'GET /api/v1/connections/2/metadata/schemas': {
        status: 404,
        body: { type: 'about:blank', title: 'No encontrada', status: 404, code: 'not_found' },
      },
    });
    const user = userEvent.setup();

    await openTab(user);
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Fichero' }), UPLOAD.id);
    await user.selectOptions(screen.getByRole('combobox', { name: 'Conexión destino' }), 'destino');

    expect(
      await screen.findByText('No se pudo leer el catálogo de la conexión: escríbelo a mano.'),
    ).toBeInTheDocument();
    await user.type(screen.getByRole('combobox', { name: /Schema destino/ }), 'ventas');
    await user.type(screen.getByRole('combobox', { name: 'Tabla destino' }), 'pedidos');
    expect(screen.getByRole('button', { name: 'Vista previa' })).toBeEnabled();
  });

  it('explica cómo se leen el separador y la codificación del CSV', async () => {
    stubTab();
    const user = userEvent.setup();

    await openTab(user);
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Fichero' }), UPLOAD.id);

    expect(await screen.findByText(/Se detectan solos: el separador/)).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Separador' })).toHaveDisplayValue('Automático (;)');
  });

  it('en un insert ofrece ajustar el contador y, en PostgreSQL, conservar los ids identity', async () => {
    const fetchMock = stubTab();
    const user = userEvent.setup();

    await openTab(user);
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Fichero' }), UPLOAD.id);
    await user.selectOptions(screen.getByRole('combobox', { name: 'Conexión destino' }), 'destino');
    await user.type(screen.getByRole('combobox', { name: 'Tabla destino' }), 'clientes');

    expect(screen.getByText(/pon la clave primaria en «\(no cargar\)»/)).toBeInTheDocument();
    // Fuera del insert no aplican: ni se ofrecen ni se envían.
    await user.selectOptions(screen.getByRole('combobox', { name: 'Operación' }), 'update');
    expect(screen.queryByRole('switch', { name: /Ajustar el contador/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('switch', { name: /Conservar los valores/ })).not.toBeInTheDocument();
    await user.selectOptions(screen.getByRole('combobox', { name: 'Operación' }), 'insert');

    expect(
      screen.getByRole('switch', { name: /^Ajustar el contador de la clave primaria tras cargar/ }),
    ).toBeChecked();
    const identity = screen.getByRole('switch', { name: /^Conservar los valores de columnas identity/ });
    expect(identity).not.toBeChecked();
    await user.click(identity);
    await user.click(screen.getByRole('button', { name: 'Vista previa' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')).toHaveLength(1));
    const body = (await callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')[0]?.json()) as {
      params: Record<string, unknown>;
    };
    expect(body.params).toMatchObject({
      operation: 'insert',
      sync_pk_sequences: true,
      override_identity: true,
    });
  });

  it('sin columnas de la tabla, el mapeo se escribe a mano', async () => {
    stubTab();
    const user = userEvent.setup();

    await openTab(user);
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Fichero' }), UPLOAD.id);
    expect(await screen.findByRole('textbox', { name: 'Columna de la tabla para «ID»' })).toHaveValue('ID');
    expect(screen.getByRole('button', { name: 'Vista previa' })).toBeDisabled();
  });
});
