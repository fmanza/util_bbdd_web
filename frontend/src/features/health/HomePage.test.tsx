import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { renderRoute } from '../../test/render';

function stubFetch(status: number, body: unknown) {
  const fetchMock = vi.fn(
    async (_request: Request) =>
      new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': status < 400 ? 'application/json' : 'application/problem+json' },
      }),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('HomePage', () => {
  it('muestra el estado y las versiones cuando la API responde', async () => {
    const fetchMock = stubFetch(200, {
      status: 'ok',
      version: '0.1.0',
      util_bbdd_version: '4.0.0',
      database: 'ok',
    });

    renderRoute('/');

    expect(await screen.findByText('Servicio operativo')).toBeInTheDocument();
    expect(screen.getByText('4.0.0')).toBeInTheDocument();
    expect(fetchMock.mock.calls[0]?.[0].url).toMatch(/\/api\/health$/);
  });

  it('avisa si la API no responde', async () => {
    stubFetch(500, { title: 'Error interno', status: 500 });

    renderRoute('/');

    expect(await screen.findByText('No se puede contactar con la API')).toBeInTheDocument();
  });

  it('muestra la página 404 de la SPA en rutas desconocidas', () => {
    stubFetch(200, {});

    renderRoute('/no-existe');

    expect(screen.getByText('Página no encontrada')).toBeInTheDocument();
  });
});
