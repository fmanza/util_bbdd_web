import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ApiError, unwrap } from '../api/client';
import { setLanguage } from '../i18n';
import { renderWithProviders } from '../test/render';
import { ErrorAlert } from './ErrorAlert';

describe('ErrorAlert', () => {
  it('muestra título, detalle y la referencia de la petición', () => {
    renderWithProviders(
      <ErrorAlert
        error={
          new ApiError({
            title: 'Demasiadas peticiones',
            status: 429,
            code: 'core.rate_limited',
            detail: 'Espera 30 s antes de reintentar.',
            request_id: '01JREQREQREQREQREQREQREQRE',
          })
        }
      />,
    );
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('Demasiadas peticiones');
    expect(alert).toHaveTextContent('Espera 30 s antes de reintentar.');
    expect(alert).toHaveTextContent('Referencia: 01JREQREQREQREQREQREQREQRE');
  });

  it('muestra el título de la API en el idioma en que responde (también en inglés)', async () => {
    await setLanguage('en');
    try {
      renderWithProviders(
        <ErrorAlert
          error={new ApiError({ title: 'Project not found', status: 404, code: 'project_not_found' })}
        />,
      );
      expect(screen.getByRole('alert')).toHaveTextContent('Project not found');
    } finally {
      await setLanguage('es');
    }
  });

  it('una respuesta sin code (proxy) toma el título por estado HTTP', () => {
    renderWithProviders(<ErrorAlert error={new ApiError({ title: 'Bad Gateway', status: 502 })} />);
    expect(screen.getByRole('alert')).not.toHaveTextContent('Bad Gateway');
  });

  it('sin referencia no muestra la línea', () => {
    renderWithProviders(<ErrorAlert error={new ApiError({ title: 'Conflicto', status: 409 })} />);
    expect(screen.getByRole('alert')).not.toHaveTextContent('Referencia');
  });
});

describe('unwrap', () => {
  it('toma la referencia de la cabecera si la respuesta no trae problem details', () => {
    const response = new Response(null, { status: 502, headers: { 'X-Request-ID': 'proxy-12345678' } });
    expect(() => unwrap({ error: undefined, response })).toThrow(ApiError);
    try {
      unwrap({ error: undefined, response });
    } catch (error) {
      expect((error as ApiError).problem.request_id).toBe('proxy-12345678');
    }
  });
});
