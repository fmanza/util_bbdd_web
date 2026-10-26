import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi } from '../../test/api';
import { stubEventSource } from '../../test/eventSource';
import {
  DOC_RUN,
  DOCUMENTATION,
  GRAPH_RUN,
  NOOP,
  ORACLE_CONNECTION,
  PROJECT,
  RUN,
  RUN_ID,
  SITE_URL,
} from '../../test/fixtures_runs';
import { renderRoute } from '../../test/render';

describe('formulario de documentación', () => {
  it('agrupa los parámetros, ofrece opciones y avisa del schema en Oracle', async () => {
    stubEventSource();
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/projects/5': { body: PROJECT },
      'GET /api/v1/projects/5/runs': { body: { items: [], total: 0 } },
      'GET /api/v1/projects/5/connections': { body: [ORACLE_CONNECTION] },
      'GET /api/v1/operations': { body: [NOOP, DOCUMENTATION] },
      'POST /api/v1/projects/5/runs': { status: 202, body: { ...RUN, status: 'queued' } },
      [`GET /api/v1/runs/${RUN_ID}`]: { body: { ...DOC_RUN, status: 'queued', artifacts: [] } },
    });
    const user = userEvent.setup();

    renderRoute('/projects/5');
    await user.click(await screen.findByRole('button', { name: 'Lanzar ejecución' }));
    const dialog = await screen.findByRole('dialog');
    await user.selectOptions(
      await within(dialog).findByRole('combobox', { name: 'Operación' }),
      'documentation',
    );

    expect(await within(dialog).findByRole('group', { name: 'Formatos' })).toBeInTheDocument();
    expect(within(dialog).getByRole('group', { name: 'Diagramas' })).toBeInTheDocument();

    await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Conexión' }), 'ventas');
    // util_bbdd 4.1.0 lee en Oracle otro owner que el usuario (GAPS G21): ya no hay aviso
    expect(within(dialog).queryByText('Oracle: solo el schema del usuario')).not.toBeInTheDocument();
    await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Dirección' }), 'outgoing');
    const columns = within(dialog).getByRole('combobox', { name: 'Columnas en el diagrama' });
    expect(columns).toHaveValue('relations_first');
    expect(
      within(columns).getByRole('option', { name: 'Primero las de relación, luego el resto' }),
    ).toBeInTheDocument();
    await user.selectOptions(columns, 'all');
    await user.click(within(dialog).getByRole('button', { name: 'Lanzar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')).toHaveLength(1));
    expect(await callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')[0]?.json()).toEqual({
      operation: 'documentation',
      params: {
        connection: 'ventas',
        word: true,
        html: true,
        graph_direction: 'outgoing',
        graph_columns: 'all',
      },
    });
  });
});

describe('resultados de la documentación', () => {
  it('muestra el sitio en un iframe con scripts y origen opaco, y descargas de Word y Excel', async () => {
    stubEventSource();
    stubApi({
      ...session(ADMIN),
      [`GET /api/v1/runs/${RUN_ID}`]: { body: DOC_RUN },
      [`GET /api/v1/runs/${RUN_ID}/artifacts/25/preview`]: { text: '# Hola\n\n<script>alert(1)</script>' },
    });

    renderRoute(`/runs/${RUN_ID}`);

    const site = await screen.findByTitle('Sitio HTML de la documentación');
    expect(site).toHaveAttribute('src', SITE_URL);
    expect(site).toHaveAttribute('sandbox', 'allow-scripts allow-popups allow-downloads');
    expect(site.getAttribute('sandbox')).not.toContain('allow-same-origin');
    const open = screen.getByRole('link', { name: 'Abrir en pestaña nueva' });
    expect(open).toHaveAttribute('href', SITE_URL);
    expect(open).toHaveAttribute('rel', 'noopener noreferrer');
    expect(screen.getByRole('link', { name: 'Descargar documentacion.docx' })).toHaveAttribute(
      'href',
      `/api/v1/runs/${RUN_ID}/artifacts/21`,
    );
    expect(screen.getByRole('link', { name: 'Descargar documentacion.xlsx' })).toBeInTheDocument();

    // Los ficheros del sitio no se listan; el Markdown se renderiza en un iframe sin permisos.
    expect(
      screen.getByText('2 ficheros del sitio HTML: ábrelo en la tarjeta de arriba.'),
    ).toBeInTheDocument();
    expect(screen.queryByText('sql-highlight.js')).not.toBeInTheDocument();
    const markdown = await screen.findByTitle('Vista previa de outputs/markdown/resumen.md');
    expect(markdown).toHaveAttribute('sandbox', '');
    expect(markdown.getAttribute('srcdoc')).toContain('<h1>Hola</h1>');
    expect(markdown.getAttribute('srcdoc')).toContain("default-src 'none'");
  });

  it('muestra la galería de un grafo de relaciones', async () => {
    stubEventSource();
    stubApi({ ...session(ADMIN), [`GET /api/v1/runs/${RUN_ID}`]: { body: GRAPH_RUN } });

    renderRoute(`/runs/${RUN_ID}`);

    expect(await screen.findByRole('heading', { name: '2 grafos' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Grafo de relaciones pedidos.svg' })).toHaveAttribute(
      'src',
      `/api/v1/runs/${RUN_ID}/artifacts/31/preview`,
    );
    expect(screen.queryByTitle('Sitio HTML de la documentación')).not.toBeInTheDocument();
  });
});
