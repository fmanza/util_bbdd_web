import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { session, stubApi, USER } from '../../test/api';
import { HSQLDB_ENGINE, PG_ENGINE } from '../../test/fixtures';
import { renderRoute } from '../../test/render';

describe('EnginesPage', () => {
  it('muestra la matriz de capacidades y los drivers no instalados', async () => {
    stubApi({ ...session(USER), 'GET /api/v1/engines': { body: [PG_ENGINE, HSQLDB_ENGINE] } });

    renderRoute('/engines');

    const row = (await screen.findByRole('rowheader', { name: 'HSQLDB' })).closest('tr');
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByText(/jaydebeapi · no instalado/)).toBeInTheDocument();
    expect(within(row as HTMLElement).getAllByText('No')).toHaveLength(4);
    expect(screen.getByRole('link', { name: 'PostgreSQL' })).toHaveAttribute('href', '/engines/postgresql');
  });

  it('muestra el error de la API', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/engines': { status: 500, body: { title: 'Error interno', status: 500 } },
    });

    renderRoute('/engines');

    expect(await screen.findByRole('alert')).toHaveTextContent('Error interno');
  });
});

describe('EngineDetailPage', () => {
  it('muestra la ficha con parámetros, instalación y enlace a nueva conexión', async () => {
    stubApi({ ...session(USER), 'GET /api/v1/engines/postgresql': { body: PG_ENGINE } });

    renderRoute('/engines/postgresql');

    expect(await screen.findByRole('heading', { name: 'PostgreSQL' })).toBeInTheDocument();
    expect(screen.getByText('pip install psycopg')).toBeInTheDocument();
    expect(screen.getByText('sslmode')).toBeInTheDocument();
    expect(screen.getByText('secreto')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Nueva conexión con este motor' })).toHaveAttribute(
      'href',
      '/connections/new?db_type=postgresql',
    );
  });

  it('motor desconocido muestra el 404 de la API', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/engines/db2': { status: 404, body: { title: 'Motor no encontrado', status: 404 } },
    });

    renderRoute('/engines/db2');

    expect(await screen.findByRole('alert')).toHaveTextContent('Motor no encontrado');
  });
});
