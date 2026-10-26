import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, type StubResponse, stubApi } from '../../../test/api';
import { stubEventSource } from '../../../test/eventSource';
import {
  FINISHED,
  MIGRATION_PLAN,
  MYSQL_READ_ONLY,
  MYSQL_TARGET,
  NOOP,
  PLAN_ID,
  PLAN_RUN,
  PROJECT,
  RUN,
} from '../../../test/fixtures_runs';
import { renderRoute } from '../../../test/render';

const DRY_ID = '01JDRYDRYDRYDRYDRYDRYDRYDR';
const ALLOWED = { ...ADMIN, can_apply_ddl: true };

function dryRun(finishedAt: string, status: 'succeeded' | 'failed' = 'succeeded') {
  return {
    ...FINISHED,
    id: DRY_ID,
    operation: 'migrate_apply',
    status,
    finished_at: finishedAt,
    params: { plan_run: PLAN_ID, target_connection: 'destino', mode: 'dry_run' },
  };
}

function stubPlan({
  me = ALLOWED,
  plan = MIGRATION_PLAN,
  applications = [] as unknown[],
  role = 'owner',
  post = { status: 202, body: { ...RUN, id: DRY_ID, status: 'queued' } } as StubResponse,
} = {}) {
  stubEventSource();
  return stubApi({
    ...session(me),
    [`GET /api/v1/runs/${PLAN_ID}`]: { body: { ...PLAN_RUN, my_role: role } },
    [`GET /api/v1/runs/${PLAN_ID}/plan`]: { body: plan },
    'GET /api/v1/projects/5/connections': { body: [MYSQL_TARGET, MYSQL_READ_ONLY] },
    'GET /api/v1/projects/5/runs': { body: { items: applications, total: applications.length } },
    'POST /api/v1/projects/5/runs': post,
    [`GET /api/v1/runs/${DRY_ID}`]: {
      body: { ...dryRun(new Date().toISOString()), status: 'queued', finished_at: null, my_role: 'owner' },
    },
  });
}

describe('visor del plan', () => {
  it('resume el plan, filtra avisos, muestra tipos y resalta el SQL', async () => {
    stubPlan();
    const user = userEvent.setup();

    renderRoute(`/runs/${PLAN_ID}`);

    expect(await screen.findByText('postgresql (public) → mysql')).toBeInTheDocument();
    const warnings = screen.getByRole('table', { name: 'Avisos' });
    expect(within(warnings).getAllByRole('row')).toHaveLength(3);
    await user.selectOptions(screen.getByRole('combobox', { name: 'Severidad' }), 'WARNING');
    expect(within(screen.getByRole('table', { name: 'Avisos' })).getAllByRole('row')).toHaveLength(2);

    await user.click(screen.getByRole('tab', { name: 'Tablas (1)' }));
    await user.click(screen.getByRole('button', { name: /clientes/ }));
    expect(await screen.findByRole('cell', { name: 'integer' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'id (PK)' })).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'Sentencias (2)' }));
    await waitFor(() => expect(document.querySelector('.hljs-keyword')).not.toBeNull());
    expect(screen.getByText('Sentencia 1 de 2')).toBeInTheDocument();
  });

  it('bloquea un plan con FK entre tipos distintos en MySQL', async () => {
    stubPlan({
      plan: {
        ...MIGRATION_PLAN,
        fk_blocking: true,
        fk_mismatches: [
          {
            table: 'pedidos',
            foreign_key: 'fk_cli',
            column: 'cliente_id',
            column_type: 'DOUBLE',
            ref_table: 'clientes',
            ref_column: 'id',
            ref_type: 'INT(11)',
          },
        ],
      },
    });

    renderRoute(`/runs/${PLAN_ID}`);

    expect(await screen.findByText('Claves foráneas que el destino rechazará')).toBeInTheDocument();
    expect(screen.getByText('pedidos.cliente_id (DOUBLE)')).toBeInTheDocument();
    expect(screen.getByText('Este plan no se puede aplicar (ver los avisos de arriba).')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Modo seco' })).not.toBeInTheDocument();
  });
});

describe('aplicar un plan', () => {
  it('sin permiso o sin ser propietario se explica y no se ofrece', async () => {
    stubPlan({ me: ADMIN });
    renderRoute(`/runs/${PLAN_ID}`);
    expect(await screen.findByText(/necesitas el permiso «Puede aplicar DDL»/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Modo seco' })).not.toBeInTheDocument();
  });

  it('un editor con permiso no puede aplicar', async () => {
    stubPlan({ role: 'editor' });
    renderRoute(`/runs/${PLAN_ID}`);
    expect(
      await screen.findByText('Solo el propietario del proyecto puede aplicar migraciones.'),
    ).toBeInTheDocument();
  });

  it('lanza el modo seco solo sobre destinos del motor y no de solo lectura', async () => {
    const fetchMock = stubPlan();
    const user = userEvent.setup();

    renderRoute(`/runs/${PLAN_ID}`);
    const select = await screen.findByRole('combobox', { name: 'Conexión destino' });
    expect(within(select).queryByRole('option', { name: /lectura/ })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Aplicar…' })).toBeDisabled();
    await user.selectOptions(select, 'destino');
    expect(screen.getByText(/Lanza un modo seco correcto/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Modo seco' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')).toHaveLength(1));
    expect(await callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')[0]?.json()).toEqual({
      operation: 'migrate_apply',
      params: { plan_run: PLAN_ID, target_connection: 'destino', mode: 'dry_run' },
    });
  });

  it('con un modo seco reciente exige casilla y alias escrito antes de aplicar', async () => {
    const fetchMock = stubPlan({ applications: [dryRun(new Date().toISOString())] });
    const user = userEvent.setup();

    renderRoute(`/runs/${PLAN_ID}`);
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Conexión destino' }), 'destino');
    await user.click(screen.getByRole('button', { name: 'Aplicar…' }));
    const dialog = await screen.findByRole('dialog');
    const submit = within(dialog).getByRole('button', { name: 'Aplicar ahora' });
    expect(within(dialog).getByText('No es atómico')).toBeInTheDocument();
    expect(submit).toBeDisabled();

    await user.click(within(dialog).getByRole('checkbox', { name: /Entiendo que no es atómico/ }));
    await user.type(
      within(dialog).getByRole('textbox', { name: 'Escribe «destino» para confirmar' }),
      'Destino',
    );
    expect(submit).toBeDisabled();
    await user.clear(within(dialog).getByRole('textbox', { name: 'Escribe «destino» para confirmar' }));
    await user.type(
      within(dialog).getByRole('textbox', { name: 'Escribe «destino» para confirmar' }),
      'destino',
    );
    await user.click(submit);

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')).toHaveLength(1));
    expect(await callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')[0]?.json()).toEqual({
      operation: 'migrate_apply',
      params: {
        plan_run: PLAN_ID,
        target_connection: 'destino',
        mode: 'apply',
        dry_run_run: DRY_ID,
        confirm: 'destino',
      },
    });
  });

  it('un modo seco de hace más de una hora no permite aplicar', async () => {
    const old = new Date(Date.now() - 61 * 60 * 1000).toISOString();
    stubPlan({ applications: [dryRun(old)] });
    const user = userEvent.setup();

    renderRoute(`/runs/${PLAN_ID}`);
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Conexión destino' }), 'destino');

    expect(screen.getByRole('button', { name: 'Aplicar…' })).toBeDisabled();
    expect(screen.getByRole('table', { name: 'Modos secos y aplicaciones' })).toHaveTextContent('Modo seco');
  });
});

describe('auditoría de la Fase 7', () => {
  it('muestra dentro del modal el error de la API al aplicar', async () => {
    stubPlan({
      applications: [dryRun(new Date().toISOString())],
      post: {
        status: 422,
        body: {
          title: 'Parámetros de la ejecución no válidos',
          status: 422,
          detail: 'El modo seco tiene más de 60 minutos: repítelo.',
        },
      },
    });
    const user = userEvent.setup();

    renderRoute(`/runs/${PLAN_ID}`);
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Conexión destino' }), 'destino');
    await user.click(screen.getByRole('button', { name: 'Aplicar…' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('checkbox', { name: /Entiendo que no es atómico/ }));
    await user.type(
      within(dialog).getByRole('textbox', { name: 'Escribe «destino» para confirmar' }),
      'destino',
    );
    await user.click(within(dialog).getByRole('button', { name: 'Aplicar ahora' }));

    expect(await within(dialog).findByText(/más de 60 minutos/)).toBeInTheDocument();
  });

  it('una aplicación en curso se cancela entre sentencias tras confirmarlo', async () => {
    stubEventSource();
    const running = {
      ...dryRun(new Date().toISOString()),
      status: 'running',
      finished_at: null,
      params: { plan_run: PLAN_ID, target_connection: 'destino', mode: 'apply' },
      my_role: 'owner',
    };
    const fetchMock = stubApi({
      ...session(ALLOWED),
      [`GET /api/v1/runs/${DRY_ID}`]: { body: running },
      [`POST /api/v1/runs/${DRY_ID}/cancel`]: { status: 202, body: { ...running, cancel_requested: true } },
    });
    const user = userEvent.setup();

    renderRoute(`/runs/${DRY_ID}`);

    await user.click(await screen.findByRole('button', { name: 'Cancelar' }));
    const dialog = await screen.findByRole('dialog', { name: 'Cancelar la aplicación' });
    expect(within(dialog).getByText(/quedan en el destino/)).toBeInTheDocument();
    expect(callsTo(fetchMock, 'POST', `/api/v1/runs/${DRY_ID}/cancel`)).toHaveLength(0);
    await user.click(within(dialog).getByRole('button', { name: 'Cancelar entre sentencias' }));
    await waitFor(() => expect(callsTo(fetchMock, 'POST', `/api/v1/runs/${DRY_ID}/cancel`)).toHaveLength(1));
    expect(screen.queryByText(/no se puede cancelar/)).not.toBeInTheDocument();
  });
});

describe('informe de la aplicación', () => {
  it('muestra la sentencia que falló y que la aplicación fue parcial', async () => {
    stubEventSource();
    stubApi({
      ...session(ALLOWED),
      [`GET /api/v1/runs/${DRY_ID}`]: {
        body: {
          ...dryRun(new Date().toISOString(), 'failed'),
          params: { plan_run: PLAN_ID, target_connection: 'destino', mode: 'apply' },
          my_role: 'owner',
          error_code: 'apply_partial',
          error_message: 'Falló la sentencia 2/2',
        },
      },
      [`GET /api/v1/runs/${DRY_ID}/migration-report`]: {
        body: {
          mode: 'apply',
          statements_hash: 'a'.repeat(64),
          statements: 2,
          applied: 1,
          failed_position: 2,
          failed_statement: 'CREATE TABLE pedidos',
          error: "Table 'pedidos' already exists",
        },
      },
    });

    renderRoute(`/runs/${DRY_ID}`);

    expect(await screen.findByText('Falló la sentencia 2')).toBeInTheDocument();
    expect(screen.getByText('Sentencias aplicadas: 1 de 2.')).toBeInTheDocument();
    expect(
      screen.getByText('Las sentencias anteriores quedaron aplicadas en el destino.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ver el plan' })).toHaveAttribute('href', `/runs/${PLAN_ID}`);
    expect(screen.queryByRole('button', { name: 'Relanzar' })).not.toBeInTheDocument();
  });

  it('dice cuántas sentencias quedaron aplicadas al cancelar', async () => {
    stubEventSource();
    stubApi({
      ...session(ALLOWED),
      [`GET /api/v1/runs/${DRY_ID}`]: {
        body: {
          ...dryRun(new Date().toISOString()),
          status: 'cancelled',
          params: { plan_run: PLAN_ID, target_connection: 'destino', mode: 'apply' },
          my_role: 'owner',
          error_code: 'cancelled',
          error_message: 'Cancelada entre sentencias: quedaron aplicadas 1 de 2 en el destino.',
        },
      },
      [`GET /api/v1/runs/${DRY_ID}/migration-report`]: {
        body: { mode: 'apply', statements_hash: 'a'.repeat(64), statements: 2, applied: 1, cancelled: true },
      },
    });

    renderRoute(`/runs/${DRY_ID}`);

    expect(await screen.findByText('Cancelada entre sentencias')).toBeInTheDocument();
    expect(
      screen.getByText('Se aplicaron 1 de 2 sentencias antes de cancelar; quedan en el destino.'),
    ).toBeInTheDocument();
  });
});

describe('formulario de lanzamiento', () => {
  it('no ofrece aplicar y muestra solo las opciones del motor destino', async () => {
    stubEventSource();
    const MIGRATE_PLAN = {
      name: 'migrate_plan',
      title: 'Plan de migración DDL',
      description: 'Plan',
      form: true,
      params: [
        {
          name: 'source_connection',
          type: 'connection',
          required: true,
          default: null,
          description: 'o',
          minimum: null,
          maximum: null,
        },
        {
          name: 'target_engine',
          type: 'string',
          required: true,
          default: null,
          description: 'd',
          minimum: null,
          maximum: null,
          options: ['mariadb', 'mysql', 'postgresql'],
        },
        {
          name: 'charset',
          type: 'string',
          required: false,
          default: null,
          description: 'c',
          minimum: null,
          maximum: null,
          group: 'mysql',
        },
        {
          name: 'pg_schema',
          type: 'string',
          required: false,
          default: null,
          description: 'p',
          minimum: null,
          maximum: null,
          group: 'postgresql',
        },
      ],
    };
    const APPLY = {
      ...MIGRATE_PLAN,
      name: 'migrate_apply',
      title: 'Aplicar migración DDL',
      form: false,
      params: [],
    };
    stubApi({
      ...session(ALLOWED),
      'GET /api/v1/projects/5': { body: PROJECT },
      'GET /api/v1/projects/5/runs': { body: { items: [], total: 0 } },
      'GET /api/v1/projects/5/connections': { body: [MYSQL_TARGET] },
      'GET /api/v1/operations': { body: [NOOP, MIGRATE_PLAN, APPLY] },
    });
    const user = userEvent.setup();

    renderRoute('/projects/5');
    await user.click(await screen.findByRole('button', { name: 'Lanzar ejecución' }));
    const dialog = await screen.findByRole('dialog');
    const operation = await within(dialog).findByRole('combobox', { name: 'Operación' });
    expect(
      within(operation).queryByRole('option', { name: 'Aplicar migración DDL' }),
    ).not.toBeInTheDocument();
    await user.selectOptions(operation, 'migrate_plan');

    expect(within(dialog).queryByRole('group', { name: 'Destino MariaDB/MySQL' })).not.toBeInTheDocument();
    await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Motor destino' }), 'mysql');
    expect(within(dialog).getByRole('group', { name: 'Destino MariaDB/MySQL' })).toBeInTheDocument();
    expect(within(dialog).queryByRole('group', { name: 'Destino PostgreSQL' })).not.toBeInTheDocument();
  });
});
