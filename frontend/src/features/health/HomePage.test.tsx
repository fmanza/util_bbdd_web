import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, HEALTH, session, stubApi } from '../../test/api';
import { renderRoute } from '../../test/render';

describe('HomePage', () => {
  it('muestra el estado y las versiones cuando la API responde', async () => {
    const fetchMock = stubApi(session(ADMIN));

    renderRoute('/');

    expect(await screen.findByText('Servicio operativo')).toBeInTheDocument();
    expect(screen.getByText('4.0.0')).toBeInTheDocument();
    expect(callsTo(fetchMock, 'GET', '/api/health')).toHaveLength(1);
  });

  it('avisa si la API no responde', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/health': { status: 500, body: { title: 'Error interno', status: 500 } },
    });

    renderRoute('/');

    expect(await screen.findByText('No se puede contactar con la API')).toBeInTheDocument();
  });

  it('muestra la página 404 de la SPA en rutas desconocidas', async () => {
    stubApi({ ...HEALTH, ...session(ADMIN) });

    renderRoute('/no-existe');

    expect(await screen.findByText('Página no encontrada')).toBeInTheDocument();
  });
});
