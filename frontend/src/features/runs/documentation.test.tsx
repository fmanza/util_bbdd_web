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
import type { Artifact, RunDetail } from './useRuns';

const mdArtifact = (id: number, path: string, previewable: boolean, size = 2048): Artifact => ({
  id,
  path: `outputs/markdown/documentacion/${path}`,
  kind: 'markdown',
  mime: 'text/markdown',
  size_bytes: size,
  sha256: 'c'.repeat(64),
  created_at: '2026-10-20T08:00:04Z',
  previewable,
});

/** Documentación con los cuatro formatos, avisos por formato y plantilla Excel aplicada. */
const CARDS_RUN: RunDetail = {
  ...DOC_RUN,
  params: { connection: 'origen', word: true, excel: true, html: true, markdown: true },
  warnings: [
    'La plantilla Word no se pudo aplicar: el documento Word usa el formato por defecto.',
    'Aviso general de la ejecución.',
  ],
  warnings_by_format: {
    word: ['La plantilla Word no se pudo aplicar: el documento Word usa el formato por defecto.'],
  },
  templates_applied: { word: false, excel: true },
  artifacts: [
    ...DOC_RUN.artifacts.filter((a) => a.kind !== 'markdown'),
    mdArtifact(71, 'docs/index.md', true),
    mdArtifact(72, 'docs/tables/pedidos.md', true),
    mdArtifact(73, 'docs/catalog.json', false, 3_600_000),
    mdArtifact(74, 'docs/llms-full.txt', false, 12_000_000),
    mdArtifact(75, 'docs/assets/javascripts/mermaid.min.js', false, 5_500_000),
    mdArtifact(76, 'mkdocs.yml', false),
    mdArtifact(77, 'README.md', true),
  ],
};

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
        table_frontier: true,
        graph_direction: 'outgoing',
        graph_columns: 'all',
      },
    });
  });
});

describe('filtro de tablas del formulario (util_bbdd 5.5.0)', () => {
  it('prueba los patrones con las tablas del schema y envía el filtro', async () => {
    stubEventSource();
    const base = `/api/v1/connections/${ORACLE_CONNECTION.connection_id}`;
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/projects/5': { body: PROJECT },
      'GET /api/v1/projects/5/runs': { body: { items: [], total: 0 } },
      'GET /api/v1/projects/5/connections': { body: [ORACLE_CONNECTION] },
      'GET /api/v1/operations': { body: [NOOP, DOCUMENTATION] },
      [`GET ${base}/metadata/schemas`]: { body: { default: 'VENTAS', schemas: [] } },
      [`GET ${base}/metadata/schemas/VENTAS`]: {
        body: {
          engine: 'oracle',
          schema_name: 'VENTAS',
          database: null,
          fetched_at: '2026-11-12T10:00:00Z',
          size_bytes: 10,
          tables: ['MVG_PEDIDO', 'MVG_PEDIDO_BAK', 'COB_LINEA'].map((name) => ({
            name,
            comment: null,
            columns: 2,
          })),
          views: [{ name: 'MVG_V', comment: null, materialized: false }],
          routines: [],
        },
      },
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
    const filter = await within(dialog).findByRole('group', { name: 'Filtro de tablas' });
    // Sin conexión no se puede probar; la ayuda, sí
    expect(within(filter).getByRole('button', { name: 'Probar patrones' })).toBeDisabled();
    await user.click(within(filter).getByRole('button', { name: 'Cómo escribir los patrones' }));
    expect(within(filter).getByText(/solo el módulo MVG/)).toBeInTheDocument();

    await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Conexión' }), 'ventas');
    await user.type(within(filter).getByRole('textbox', { name: 'Incluir (patrones)' }), 'mvg_*');
    await user.type(within(filter).getByRole('textbox', { name: 'Excluir (patrones)' }), '*_BAK');
    await user.click(within(filter).getByRole('button', { name: 'Probar patrones' }));

    expect(
      await within(filter).findByText('Se documentan 1 de 3 tablas y 1 de 1 vistas.'),
    ).toBeInTheDocument();
    expect(within(filter).getByText('MVG_PEDIDO, MVG_V')).toBeInTheDocument();
    expect(within(filter).getByText('MVG_PEDIDO_BAK, COB_LINEA')).toBeInTheDocument();

    await user.click(within(dialog).getByRole('button', { name: 'Lanzar' }));
    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')).toHaveLength(1));
    expect(await callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')[0]?.json()).toMatchObject({
      params: {
        connection: 'ventas',
        table_include: 'mvg_*',
        table_exclude: '*_BAK',
        table_frontier: true,
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

  it('una tarjeta por formato con su ZIP, sus avisos y su plantilla; la lista sin la carpeta Markdown', async () => {
    stubEventSource();
    stubApi({
      ...session(ADMIN),
      [`GET /api/v1/runs/${RUN_ID}`]: { body: CARDS_RUN },
      [`GET /api/v1/runs/${RUN_ID}/artifacts/71/preview`]: { text: '# Portada' },
    });

    renderRoute(`/runs/${RUN_ID}`);

    const word = await screen.findByRole('region', { name: 'Word' });
    const excel = screen.getByRole('region', { name: 'Excel' });
    const html = screen.getByRole('region', { name: 'HTML' });
    const markdown = screen.getByRole('region', { name: 'Markdown' });
    for (const [card, format] of [
      [word, 'word'],
      [excel, 'excel'],
      [html, 'html'],
      [markdown, 'markdown'],
    ] as const) {
      expect(within(card).getByRole('link', { name: /^Descargar ZIP de / })).toHaveAttribute(
        'href',
        `/api/v1/runs/${RUN_ID}/archive?format=${format}`,
      );
    }
    // Avisos: el de Word en su tarjeta, el resto en la cabecera.
    expect(within(word).getByText(/La plantilla Word no se pudo aplicar/)).toBeInTheDocument();
    expect(screen.getAllByText(/La plantilla Word no se pudo aplicar/)).toHaveLength(1);
    expect(screen.getByText('Aviso general de la ejecución.')).toBeInTheDocument();
    expect(within(excel).getByText('Con plantilla')).toBeInTheDocument();
    expect(within(word).queryByText('Con plantilla')).not.toBeInTheDocument();
    expect(within(html).getByTitle('Sitio HTML de la documentación')).toHaveAttribute('src', SITE_URL);
    // Markdown: auxiliares para descargar (sin mermaid.min.js) y portada en el iframe sin permisos.
    expect(within(markdown).getByText('2 páginas')).toBeInTheDocument();
    expect(within(markdown).getByRole('link', { name: 'Descargar catalog.json' })).toHaveAttribute(
      'href',
      `/api/v1/runs/${RUN_ID}/artifacts/73`,
    );
    expect(within(markdown).getByRole('link', { name: 'Descargar mkdocs.yml' })).toBeInTheDocument();
    // README.md (util_bbdd 5.5.0): aviso con su descarga; no es una página del visor (sigue en 2 páginas)
    expect(within(markdown).getByText('Cómo ver la documentación fuera de la web')).toBeInTheDocument();
    expect(within(markdown).getByRole('link', { name: 'Descargar README.md' })).toHaveAttribute(
      'href',
      `/api/v1/runs/${RUN_ID}/artifacts/77`,
    );
    expect(
      within(markdown).queryByRole('link', { name: 'Descargar mermaid.min.js' }),
    ).not.toBeInTheDocument();
    const index = await within(markdown).findByTitle('Página Markdown index.md');
    expect(index.getAttribute('srcdoc')).toContain('<h1>Portada</h1>');
    // El navegador de artefactos no lista la carpeta Markdown.
    expect(
      screen.getByText('7 ficheros de la documentación Markdown: ábrelos en su tarjeta.'),
    ).toBeInTheDocument();
    expect(screen.queryByText('pedidos.md')).not.toBeInTheDocument();
  });

  it('muestra un formato pedido sin ficheros y ninguno no pedido', async () => {
    stubEventSource();
    stubApi({
      ...session(ADMIN),
      [`GET /api/v1/runs/${RUN_ID}`]: {
        body: {
          ...DOC_RUN,
          params: { connection: 'origen', word: true, excel: false, html: false, markdown: false },
          site_url: null,
          artifacts: [],
        },
      },
    });

    renderRoute(`/runs/${RUN_ID}`);

    const word = await screen.findByRole('region', { name: 'Word' });
    expect(within(word).getByText('Sin ficheros: este formato no llegó a generarse.')).toBeInTheDocument();
    expect(within(word).queryByRole('link', { name: /ZIP/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Excel' })).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Markdown' })).not.toBeInTheDocument();
  });

  it('una vista previa demasiado grande muestra el mensaje de la API', async () => {
    stubEventSource();
    stubApi({
      ...session(ADMIN),
      [`GET /api/v1/runs/${RUN_ID}`]: { body: DOC_RUN },
      [`GET /api/v1/runs/${RUN_ID}/artifacts/25/preview`]: {
        status: 413,
        body: { title: 'El artefacto es demasiado grande para la vista previa; descárgalo', status: 413 },
      },
    });

    renderRoute(`/runs/${RUN_ID}`);

    expect(
      await screen.findByText('El artefacto es demasiado grande para la vista previa; descárgalo'),
    ).toBeInTheDocument();
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
