import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi, USER } from '../../test/api';
import { renderRoute } from '../../test/render';
import type { MyStorage, StorageSettings, Usage } from './useStorage';

const MB = 1024 * 1024;
const URL = '/api/v1/admin/storage';

const SETTINGS: StorageSettings = {
  user_quota_mb: { value: 500, default: 1024, overridden: true },
  run_retention_days: { value: 30, default: 30, overridden: false },
  run_retention_per_project: { value: 100, default: 100, overridden: false },
  upload_retention_days: { value: 7, default: 7, overridden: false },
  quota_purge: { value: false, default: false, overridden: false },
  quota_purge_target_pct: { value: 80, default: 80, overridden: false },
};

const ANA_USAGE: Usage = {
  user_id: 2,
  username: 'ana',
  display_name: 'Ana',
  run_bytes: 400 * MB,
  upload_bytes: 50 * MB,
  used_bytes: 450 * MB,
  quota_bytes: 500 * MB,
  quota_source: 'global',
  used_pct: 90,
};

function stubAdmin(settings: StorageSettings | 'error' = SETTINGS) {
  return stubApi({
    ...session(ADMIN),
    [`GET ${URL}`]:
      settings === 'error'
        ? { status: 500, body: { title: 'Error interno', status: 500 } }
        : { body: settings },
    [`PATCH ${URL}`]: { body: SETTINGS },
    [`POST ${URL}/preview`]: {
      body: { runs: 3, run_bytes: 30 * MB, uploads: 1, upload_bytes: MB, users: 2 },
    },
    [`POST ${URL}/maintenance`]: { status: 202, body: null },
    [`GET ${URL}/usage`]: {
      body: {
        items: [ANA_USAGE, { ...ANA_USAGE, user_id: 3, username: 'luis', quota_bytes: null, used_pct: null }],
        total: 2,
      },
    },
  });
}

describe('Administración → Almacenamiento', () => {
  it('guarda un ajuste tras confirmar lo que se purgará', async () => {
    const fetchMock = stubAdmin();
    const user = userEvent.setup();

    renderRoute('/admin/storage');
    const quota = await screen.findByRole('textbox', { name: 'Cuota por usuario (MB)' });
    expect(screen.getByText(/Por defecto: 1024 \(UBW_USER_QUOTA_MB\)/)).toBeInTheDocument();
    await user.clear(quota);
    await user.type(quota, '300');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    const dialog = await screen.findByRole('dialog', { name: 'Confirmar los ajustes' });
    expect(within(dialog).getByText(/purgará 3 ejecuciones .* de 2 usuarios/)).toBeInTheDocument();
    expect(await callsTo(fetchMock, 'POST', `${URL}/preview`)[0]?.json()).toEqual({ user_quota_mb: 300 });
    expect(callsTo(fetchMock, 'PATCH', URL)).toHaveLength(0);
    await user.click(within(dialog).getByRole('button', { name: 'Guardar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'PATCH', URL)).toHaveLength(1));
    expect(await callsTo(fetchMock, 'PATCH', URL)[0]?.json()).toEqual({ user_quota_mb: 300 });
  });

  it('restablece un ajuste a su variable UBW_*', async () => {
    const fetchMock = stubAdmin();
    const user = userEvent.setup();

    renderRoute('/admin/storage');
    await user.click(await screen.findByRole('button', { name: 'Restablecer Cuota por usuario (MB)' }));
    expect(screen.getByText('Volverá al valor por defecto al guardar.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Guardar' }));
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Guardar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'PATCH', URL)).toHaveLength(1));
    expect(await callsTo(fetchMock, 'PATCH', URL)[0]?.json()).toEqual({ user_quota_mb: null });
  });

  it('pide aplicar ya la retención y muestra el uso por usuario', async () => {
    const fetchMock = stubAdmin();
    const user = userEvent.setup();

    renderRoute('/admin/storage');
    const table = await screen.findByRole('table', { name: 'Uso por usuario' });
    expect(within(table).getByRole('progressbar', { name: 'ana: 90 % de su cuota' })).toBeInTheDocument();
    expect(within(table).getByText('Sin límite')).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Objetivo de la purga' })).toBeDisabled();

    await user.click(screen.getByRole('button', { name: 'Aplicar ahora' }));
    await waitFor(() => expect(callsTo(fetchMock, 'POST', `${URL}/maintenance`)).toHaveLength(1));
    expect(await screen.findByRole('status')).toHaveTextContent('aplicará la retención');
  });

  it('muestra el error si no se pueden cargar los ajustes', async () => {
    stubAdmin('error');

    renderRoute('/admin/storage');

    expect(await screen.findByText('Error interno')).toBeInTheDocument();
  });
});

describe('Mi espacio', () => {
  const MINE: MyStorage = {
    run_bytes: 400 * MB,
    upload_bytes: 50 * MB,
    used_bytes: 450 * MB,
    quota_bytes: 500 * MB,
    quota_source: 'user',
    used_pct: 90,
    quota_purge: true,
    quota_purge_target_pct: 80,
  };

  it('muestra el uso, el aviso de poco espacio y la purga automática', async () => {
    stubApi({ ...session(USER), 'GET /api/v1/auth/me/storage': { body: MINE } });

    renderRoute('/account/storage');

    expect(await screen.findByRole('progressbar', { name: '90 % de tu cuota' })).toBeInTheDocument();
    expect(screen.getByText('Cuota asignada a tu cuenta.')).toBeInTheDocument();
    expect(screen.getByText('Te queda poco espacio')).toBeInTheDocument();
    expect(screen.getByText(/hasta bajar al 80 %/)).toBeInTheDocument();
  });

  it('sin límite no muestra barra ni avisos', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/auth/me/storage': {
        body: { ...MINE, quota_bytes: null, quota_source: 'unlimited', used_pct: null, quota_purge: false },
      },
    });

    renderRoute('/account/storage');

    expect(await screen.findByText(/no tiene límite de espacio/)).toBeInTheDocument();
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    expect(screen.queryByText('Te queda poco espacio')).not.toBeInTheDocument();
  });
});

describe('cuota de un usuario', () => {
  const ANA = {
    id: 2,
    username: 'ana',
    display_name: 'Ana',
    role: 'user',
    is_active: true,
    can_run_sql: false,
    can_apply_ddl: false,
    can_write_data: false,
    storage_quota_mb: null,
    locked_until: null,
    password_changed_at: '2026-10-20T08:00:00Z',
    created_at: '2026-10-20T08:00:00Z',
    updated_at: '2026-10-20T08:00:00Z',
  };

  it('asigna una cuota propia y vuelve a la global', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': {
        body: { items: [ANA, { ...ANA, id: 3, username: 'luis', storage_quota_mb: 0 }], total: 2 },
      },
      'PATCH /api/v1/users/2': { body: ANA },
      'PATCH /api/v1/users/3': { body: ANA },
    });
    const user = userEvent.setup();

    renderRoute('/admin/users');
    await user.click(await screen.findByRole('button', { name: 'Editar ana' }));
    let dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('switch', { name: /Usar la cuota global/ }));
    const quota = within(dialog).getByRole('textbox', { name: /Cuota propia/ });
    await user.clear(quota);
    await user.type(quota, '2048');
    await user.click(within(dialog).getByRole('button', { name: 'Guardar' }));
    await waitFor(() => expect(callsTo(fetchMock, 'PATCH', '/api/v1/users/2')).toHaveLength(1));
    expect(await callsTo(fetchMock, 'PATCH', '/api/v1/users/2')[0]?.json()).toEqual({
      storage_quota_mb: 2048,
    });

    await user.click(await screen.findByRole('button', { name: 'Editar luis' }));
    dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('switch', { name: /Usar la cuota global/ }));
    await user.click(within(dialog).getByRole('button', { name: 'Guardar' }));
    await waitFor(() => expect(callsTo(fetchMock, 'PATCH', '/api/v1/users/3')).toHaveLength(1));
    expect(await callsTo(fetchMock, 'PATCH', '/api/v1/users/3')[0]?.json()).toEqual({
      storage_quota_mb: null,
    });
  });
});
