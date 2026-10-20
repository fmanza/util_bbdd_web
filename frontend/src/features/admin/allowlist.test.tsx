import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi, USER } from '../../test/api';
import { renderRoute } from '../../test/render';

const ENTRY = { id: 3, pattern: '10.0.0.0/8', description: 'LAN', created_at: '2026-10-20T08:00:00Z' };

describe('AllowlistPage', () => {
  it('avisa de que la lista vacía bloquea todas las conexiones', async () => {
    stubApi({ ...session(ADMIN), 'GET /api/v1/admin/allowlist': { body: [] } });

    renderRoute('/admin/allowlist');

    expect(await screen.findByText(/ninguna conexión de red puede probarse/)).toBeInTheDocument();
  });

  it('añade un destino y valida el campo', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/allowlist': { body: [] },
      'POST /api/v1/admin/allowlist': { status: 201, body: ENTRY },
    });
    const user = userEvent.setup();

    renderRoute('/admin/allowlist');
    await user.click(await screen.findByRole('button', { name: 'Añadir destino' }));
    expect(await screen.findByText('Campo obligatorio')).toBeInTheDocument();

    await user.type(screen.getByRole('textbox', { name: /^Destino/ }), '10.0.0.0/8');
    await user.type(screen.getByRole('textbox', { name: 'Descripción' }), 'LAN');
    await user.click(screen.getByRole('button', { name: 'Añadir destino' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/admin/allowlist')).toHaveLength(1));
    expect(await callsTo(fetchMock, 'POST', '/api/v1/admin/allowlist')[0]?.json()).toEqual({
      pattern: '10.0.0.0/8',
      description: 'LAN',
    });
  });

  it('quita un destino tras confirmar', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/allowlist': { body: [ENTRY] },
      'DELETE /api/v1/admin/allowlist/3': { status: 204 },
    });
    const user = userEvent.setup();

    renderRoute('/admin/allowlist');
    await user.click(await screen.findByRole('button', { name: 'Quitar 10.0.0.0/8' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Quitar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'DELETE', '/api/v1/admin/allowlist/3')).toHaveLength(1));
  });

  it('un usuario sin rol admin no tiene acceso', async () => {
    stubApi(session(USER));

    renderRoute('/admin/allowlist');

    expect(await screen.findByText('Sin permiso')).toBeInTheDocument();
  });
});
