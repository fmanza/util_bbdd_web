import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi, USER } from '../../test/api';
import { CONNECTION } from '../../test/fixtures';
import { PROJECT } from '../../test/fixtures_runs';
import { renderRoute } from '../../test/render';

const BASE = '/api/v1/connections/7';
const TREE = {
  engine: 'sqlite',
  schema_name: 'main',
  database: { version: '3.53' },
  fetched_at: '2026-10-22T08:00:00Z',
  size_bytes: 1000,
  tables: [
    { name: 'clientes', comment: null, columns: 3 },
    { name: 'pedidos', comment: null, columns: 3 },
  ],
  views: [{ name: 'v_pedidos', comment: null, materialized: false }],
  routines: [],
};
const PEDIDOS = {
  name: 'pedidos',
  comment: null,
  fetched_at: '2026-10-22T08:00:00Z',
  columns: [
    { name: 'id', ordinal: 1, data_type: 'INTEGER', nullable: false, identity: 'by default' },
    { name: 'cliente_id', ordinal: 2, data_type: 'INTEGER', nullable: false },
    { name: 'total', ordinal: 3, data_type: 'NUMERIC(10,2)', nullable: true, default: '0' },
  ],
  primary_key: { name: '', columns: ['id'] },
  uniques: [],
  checks: [{ name: '', expression: 'total >= 0' }],
  indexes: [{ name: 'ix_pedidos_cliente', columns: ['cliente_id'], unique: false }],
  foreign_keys: [
    {
      table: 'pedidos',
      name: '',
      columns: ['cliente_id'],
      ref_schema: 'main',
      ref_table: 'clientes',
      ref_columns: ['id'],
      on_delete: 'CASCADE',
      on_update: 'NO ACTION',
    },
  ],
  referenced_by: [],
};
const RESULT = {
  columns: ['id', 'total'],
  rows: [
    [10, '9.50'],
    [11, null],
  ],
  truncated: true,
  row_count: 2,
  duration_ms: 4,
};

const EXPLORER = {
  [`GET ${BASE}`]: { body: CONNECTION },
  [`GET ${BASE}/metadata/schemas`]: {
    body: {
      default: 'main',
      schemas: [
        { name: 'main', system: false, cached: true },
        { name: 'information_schema', system: true, cached: false },
      ],
    },
  },
  [`GET ${BASE}/metadata/schemas/main`]: { body: TREE },
  [`GET ${BASE}/metadata/schemas/main/tables/pedidos`]: { body: PEDIDOS },
  [`GET ${BASE}/metadata/schemas/main/ddl`]: {
    body: { kind: 'table', name: 'pedidos', ddl: 'CREATE TABLE pedidos (…)' },
  },
};

describe('ExplorerPage', () => {
  it('muestra el árbol, oculta schemas del sistema y abre el detalle de una tabla', async () => {
    stubApi({ ...session(USER), ...EXPLORER });
    const user = userEvent.setup();

    renderRoute('/connections/7/explore');

    const schema = await screen.findByRole('combobox', { name: 'Schema' });
    expect(within(schema).queryByText(/information_schema/)).not.toBeInTheDocument();
    await user.click(await screen.findByText('pedidos'));

    expect(await screen.findByRole('tab', { name: 'Columnas (3)' })).toBeInTheDocument();
    expect(screen.getByText('NUMERIC(10,2)')).toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: 'Relaciones (1)' }));
    expect(await screen.findByRole('button', { name: 'clientes' })).toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: 'DDL' }));
    expect(await screen.findByText('CREATE TABLE pedidos (…)')).toBeInTheDocument();

    await user.click(screen.getByRole('checkbox', { name: 'Mostrar schemas del sistema' }));
    expect(within(schema).getByText('information_schema (sistema)')).toBeInTheDocument();
  });

  it('filtra objetos y refresca la caché', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      ...EXPLORER,
      [`DELETE ${BASE}/metadata/schemas/main`]: { status: 204 },
    });
    const user = userEvent.setup();

    renderRoute('/connections/7/explore');
    await screen.findByText('pedidos');
    await user.type(screen.getByRole('textbox', { name: 'Filtrar objetos' }), 'clie');
    expect(screen.queryByText('pedidos')).not.toBeInTheDocument();
    expect(screen.getByText('Tablas (1)')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Refrescar' }));
    await waitFor(() =>
      expect(callsTo(fetchMock, 'DELETE', `${BASE}/metadata/schemas/main`)).toHaveLength(1),
    );
  });

  it('muestra el error saneado si no se puede conectar', async () => {
    stubApi({
      ...session(USER),
      [`GET ${BASE}`]: { body: CONNECTION },
      [`GET ${BASE}/metadata/schemas`]: {
        status: 502,
        body: {
          title: 'No se pudo consultar la base de datos',
          status: 502,
          detail: 'El destino no está en la lista…',
          code: 'not_allowed',
        },
      },
    });

    renderRoute('/connections/7/explore');

    expect(await screen.findByRole('alert')).toHaveTextContent('El destino no está en la lista');
  });

  it('ejecuta una query nombrada y marca el parámetro rechazado', async () => {
    let call = 0;
    const fetchMock = stubApi({
      ...session(USER),
      ...EXPLORER,
      [`GET ${BASE}/queries`]: {
        body: [
          {
            id: 3,
            db_type: 'sqlite',
            name: 'pedidos_por_cliente',
            description: 'Pedidos de un cliente',
            params: ['cliente'],
            sql_template: 'SELECT …',
            created_at: '2026-10-22T08:00:00Z',
            updated_at: '2026-10-22T08:00:00Z',
          },
        ],
      },
      [`POST ${BASE}/queries/3/run`]: () => {
        call += 1;
        return call === 1
          ? {
              status: 422,
              body: {
                title: 'Query no válida',
                status: 422,
                errors: [
                  {
                    loc: ['body', 'params', 'cliente'],
                    msg: 'Solo identificadores o números',
                    type: 'value_error',
                  },
                ],
              },
            }
          : { body: RESULT };
      },
    });
    const user = userEvent.setup();

    renderRoute('/connections/7/explore');
    await user.click(await screen.findByRole('tab', { name: 'Queries nombradas' }));
    await user.type(await screen.findByRole('textbox', { name: /^cliente/ }), '1 OR 1=1');
    await user.click(screen.getByRole('button', { name: 'Ejecutar' }));
    expect(await screen.findByText('Solo identificadores o números')).toBeInTheDocument();

    await user.clear(screen.getByRole('textbox', { name: /^cliente/ }));
    await user.type(screen.getByRole('textbox', { name: /^cliente/ }), '1');
    await user.click(screen.getByRole('button', { name: 'Ejecutar' }));
    expect(await screen.findByText('2 filas · 4 ms')).toBeInTheDocument();
    expect(screen.getByText('NULL')).toBeInTheDocument();
    expect(screen.getByText(/Resultado recortado/)).toBeInTheDocument();
    expect(await callsTo(fetchMock, 'POST', `${BASE}/queries/3/run`)[1]?.json()).toEqual({
      params: { cliente: '1' },
      limit: null,
    });
  });
});

describe('consola SQL del proyecto', () => {
  const PROJECT_ROUTES = {
    'GET /api/v1/projects/5': { body: PROJECT },
    'GET /api/v1/projects/5/runs': { body: { items: [], total: 0 } },
    'GET /api/v1/projects/5/connections': { body: [] },
  };
  const CONNS = [
    {
      alias: 'tienda',
      connection_name: 'Tienda',
      db_type: 'sqlite',
      read_only: true,
      supported: true,
      read_only_transaction: true,
    },
    {
      alias: 'erp',
      connection_name: 'ERP',
      db_type: 'sqlserver',
      read_only: true,
      supported: true,
      read_only_transaction: false,
    },
    {
      alias: 'rw',
      connection_name: 'Escritura',
      db_type: 'postgresql',
      read_only: false,
      supported: true,
      read_only_transaction: true,
    },
  ];

  it('sin permiso explica cómo conseguirlo', async () => {
    stubApi({
      ...session(USER),
      ...PROJECT_ROUTES,
      'GET /api/v1/projects/5/sql': { body: { allowed: false, reason: 'permission', connections: CONNS } },
    });

    renderRoute('/projects/5?tab=sql');

    expect(await screen.findByText(/Necesitas el permiso/)).toBeInTheDocument();
  });

  it('ejecuta SQL, avisa en SQL Server y muestra el error del motor', async () => {
    let call = 0;
    const fetchMock = stubApi({
      ...session(ADMIN),
      ...PROJECT_ROUTES,
      'GET /api/v1/projects/5/sql': { body: { allowed: true, reason: null, connections: CONNS } },
      'POST /api/v1/projects/5/connections/tienda/sql': () => {
        call += 1;
        return call === 1
          ? {
              status: 422,
              body: {
                title: 'Consulta no admitida',
                status: 422,
                detail: 'no such table: x',
                code: 'query_error',
              },
            }
          : { body: RESULT };
      },
    });
    const user = userEvent.setup();

    renderRoute('/projects/5?tab=sql');
    const select = await screen.findByRole('combobox', { name: 'Conexión' });
    expect(within(select).getByRole('option', { name: /Escritura/ })).toBeDisabled();
    await user.selectOptions(select, 'erp');
    expect(screen.getByText(/no tiene transacción de solo lectura/)).toBeInTheDocument();
    await user.selectOptions(select, 'tienda');

    await user.type(screen.getByRole('textbox', { name: /^Consulta/ }), 'SELECT * FROM x');
    await user.click(screen.getByRole('button', { name: 'Ejecutar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('no such table: x');

    await user.click(screen.getByRole('button', { name: 'Ejecutar' }));
    expect(await screen.findByText('2 filas · 4 ms')).toBeInTheDocument();
    expect(await callsTo(fetchMock, 'POST', '/api/v1/projects/5/connections/tienda/sql')[0]?.json()).toEqual({
      sql: 'SELECT * FROM x',
      limit: null,
    });
  });
});

describe('QueriesPage (admin)', () => {
  it('crea una query y muestra el error de plantilla', async () => {
    let call = 0;
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/queries': { body: [] },
      'GET /api/v1/engines': {
        body: [
          {
            db_type: 'sqlite',
            name: 'SQLite',
            description: '',
            version_range: '',
            default_port: null,
            drivers: [],
            capabilities: {
              async_supported: true,
              migrate_source: false,
              migrate_target: false,
              readiness: true,
            },
          },
        ],
      },
      'POST /api/v1/admin/queries': () => {
        call += 1;
        return call === 1
          ? {
              status: 422,
              body: {
                title: 'Query no válida',
                status: 422,
                detail: 'Solo se admiten consultas SELECT',
                errors: [
                  {
                    loc: ['body', 'sql_template'],
                    msg: 'Solo se admiten consultas SELECT',
                    type: 'value_error',
                  },
                ],
              },
            }
          : { status: 201, body: {} };
      },
    });
    const user = userEvent.setup();

    renderRoute('/admin/queries');
    await user.click(await screen.findByRole('button', { name: 'Nueva query' }));
    const dialog = await screen.findByRole('dialog');
    await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Motor' }), 'sqlite');
    await user.type(within(dialog).getByRole('textbox', { name: /^Nombre/ }), 'borrar');
    await user.type(within(dialog).getByRole('textbox', { name: /^Plantilla SQL/ }), 'DELETE FROM t');
    await user.click(within(dialog).getByRole('button', { name: 'Guardar' }));

    expect(await within(dialog).findAllByText('Solo se admiten consultas SELECT')).not.toHaveLength(0);
    expect(await callsTo(fetchMock, 'POST', '/api/v1/admin/queries')[0]?.json()).toEqual({
      db_type: 'sqlite',
      name: 'borrar',
      description: '',
      sql_template: 'DELETE FROM t',
    });
  });
});
