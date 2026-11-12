import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi } from '../../test/api';
import { stubEventSource } from '../../test/eventSource';
import {
  DOCUMENTATION,
  FINISHED,
  ORACLE_CONNECTION,
  PROJECT,
  RUN,
  RUN_ID,
  SCHEMA_DIFF,
} from '../../test/fixtures_runs';
import { renderRoute } from '../../test/render';
import { stripFrontMatter } from './markdown';
import type { Operation, RunDetail } from './useRuns';

type Param = Operation['params'][number];

const param = (name: string, type: Param['type'], extra: Partial<Param> = {}): Param => ({
  name,
  type,
  required: false,
  default: null,
  description: name,
  minimum: null,
  maximum: null,
  options: null,
  group: null,
  ...extra,
});

/** Documentación con el formato Markdown y su grupo de opciones (`requires: markdown`). */
const MARKDOWN_DOC: Operation = {
  ...DOCUMENTATION,
  params: [
    ...DOCUMENTATION.params,
    param('markdown', 'boolean', { default: false, group: 'formats' }),
    param('markdown_site_name', 'string', { group: 'markdown', requires: 'markdown' }),
    param('markdown_diagram_depth', 'integer', {
      default: 2,
      minimum: 1,
      maximum: 3,
      group: 'markdown',
      requires: 'markdown',
    }),
    param('trace_map', 'template', { group: 'markdown', requires: 'markdown', template_kind: 'trace' }),
    param('markdown_previous_run', 'run', {
      group: 'markdown',
      requires: 'markdown',
      run_operation: 'documentation',
    }),
  ],
};

const previousRun = (id: string, params: Record<string, unknown>) => ({
  ...RUN,
  id,
  operation: 'documentation',
  status: 'succeeded' as const,
  finished_at: '2026-11-01T10:00:00Z',
  params,
});

const TRACE = {
  id: '01JTRACE00000000000000000A',
  scope: 'project',
  kind: 'trace',
  name: 'Ventas',
  filename: 'ventas.toml',
  size_bytes: 100,
  sha256: 'a'.repeat(64),
  table_style: null,
  table_styles: [],
  username: 'admin',
  created_at: '2026-11-01T10:00:00Z',
  updated_at: '2026-11-01T10:00:00Z',
};

async function openForm() {
  const user = userEvent.setup();
  renderRoute('/projects/5');
  await user.click(await screen.findByRole('button', { name: 'Lanzar ejecución' }));
  const dialog = await screen.findByRole('dialog');
  await user.selectOptions(
    await within(dialog).findByRole('combobox', { name: 'Operación' }),
    'documentation',
  );
  await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Conexión' }), 'ventas');
  return { user, dialog };
}

describe('formulario de documentación Markdown', () => {
  it('muestra las opciones del Markdown solo con la casilla y ofrece las documentaciones comparables', async () => {
    stubEventSource();
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/projects/5': { body: PROJECT },
      'GET /api/v1/projects/5/runs': {
        body: {
          items: [
            previousRun('01JPREV0000000000000000001', { connection: 'ventas', schema: null, markdown: true }),
            previousRun('01JPREV0000000000000000002', {
              connection: 'ventas',
              schema: null,
              markdown: false,
            }),
            previousRun('01JPREV0000000000000000003', { connection: 'otra', schema: null, markdown: true }),
          ],
          total: 3,
        },
      },
      'GET /api/v1/projects/5/connections': { body: [ORACLE_CONNECTION] },
      'GET /api/v1/projects/5/document-templates': { body: [TRACE] },
      'GET /api/v1/operations': { body: [MARKDOWN_DOC] },
      'POST /api/v1/projects/5/runs': { status: 202, body: { ...RUN, status: 'queued' } },
      [`GET /api/v1/runs/${RUN_ID}`]: { body: { ...FINISHED, status: 'queued' } },
    });
    const { user, dialog } = await openForm();

    expect(within(dialog).queryByRole('group', { name: 'Markdown' })).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole('switch', { name: /^Markdown/ }));
    const group = await within(dialog).findByRole('group', { name: 'Markdown' });
    const trace = within(group).getByRole('combobox', { name: 'Mapa de trazabilidad' });
    expect(within(trace).getByRole('option', { name: 'Ventas' })).toBeInTheDocument();
    const previous = within(group).getByRole('combobox', { name: 'Comparar con la documentación' });
    // Solo la de la misma conexión y con Markdown.
    expect(within(previous).getAllByRole('option')).toHaveLength(2);
    await user.selectOptions(previous, '01JPREV0000000000000000001');
    await user.selectOptions(trace, TRACE.id);
    await user.type(within(group).getByRole('textbox', { name: 'Título del sitio' }), 'Ventas');
    await user.click(within(dialog).getByRole('button', { name: 'Lanzar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')).toHaveLength(1));
    const body = (await callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')[0]?.json()) as {
      params: Record<string, unknown>;
    };
    expect(body.params).toMatchObject({
      markdown: true,
      markdown_site_name: 'Ventas',
      markdown_diagram_depth: 2,
      trace_map: TRACE.id,
      markdown_previous_run: '01JPREV0000000000000000001',
    });
  });

  it('sin la casilla no envía las opciones del Markdown', async () => {
    stubEventSource();
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/projects/5': { body: PROJECT },
      'GET /api/v1/projects/5/runs': { body: { items: [], total: 0 } },
      'GET /api/v1/projects/5/connections': { body: [ORACLE_CONNECTION] },
      'GET /api/v1/projects/5/document-templates': { body: [TRACE] },
      'GET /api/v1/operations': { body: [MARKDOWN_DOC] },
      'POST /api/v1/projects/5/runs': { status: 202, body: { ...RUN, status: 'queued' } },
      [`GET /api/v1/runs/${RUN_ID}`]: { body: { ...FINISHED, status: 'queued' } },
    });
    const { user, dialog } = await openForm();

    await user.click(within(dialog).getByRole('button', { name: 'Lanzar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')).toHaveLength(1));
    const body = (await callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')[0]?.json()) as {
      params: Record<string, unknown>;
    };
    expect(body.params['markdown']).toBe(false);
    expect(body.params['trace_map']).toBeNull();
    expect(body.params['markdown_previous_run']).toBeNull();
    expect(body.params).not.toHaveProperty('markdown_diagram_depth');
    expect(body.params).not.toHaveProperty('markdown_site_name');
  });
});

const MARKDOWN_RUN: RunDetail = {
  ...FINISHED,
  operation: 'documentation',
  params: { connection: 'origen', markdown: true },
  has_diff: true,
  artifacts: [
    {
      id: 61,
      path: 'outputs/markdown/documentacion/docs/index.md',
      kind: 'markdown',
      mime: 'text/markdown',
      size_bytes: 100,
      sha256: 'c'.repeat(64),
      created_at: '2026-10-20T08:00:04Z',
      previewable: true,
    },
    {
      id: 62,
      path: 'outputs/markdown/documentacion/docs/changes.json',
      kind: 'markdown',
      mime: 'application/json',
      size_bytes: 100,
      sha256: 'c'.repeat(64),
      created_at: '2026-10-20T08:00:04Z',
      previewable: true,
    },
  ],
};

describe('opciones ocultas del Markdown', () => {
  const routes = (runs: unknown[]) => ({
    ...session(ADMIN),
    'GET /api/v1/projects/5': { body: PROJECT },
    'GET /api/v1/projects/5/runs': { body: { items: runs, total: runs.length } },
    'GET /api/v1/projects/5/connections': { body: [ORACLE_CONNECTION] },
    'GET /api/v1/projects/5/document-templates': { body: [TRACE] },
    'GET /api/v1/operations': { body: [MARKDOWN_DOC] },
    'POST /api/v1/projects/5/runs': { status: 202, body: { ...RUN, status: 'queued' } },
    [`GET /api/v1/runs/${RUN_ID}`]: { body: { ...FINISHED, status: 'queued' } },
  });

  it('un valor no válido en una opción que se oculta no bloquea el envío', async () => {
    stubEventSource();
    const fetchMock = stubApi(routes([]));
    const { user, dialog } = await openForm();
    const toggle = within(dialog).getByRole('switch', { name: /^Markdown/ });

    await user.click(toggle);
    const depth = await within(dialog).findByRole('textbox', { name: 'Tope de niveles en Markdown' });
    await user.clear(depth);
    await user.type(depth, '9');
    await user.click(toggle);
    // Oculta, la opción vuelve a su valor por defecto (y al activarlo de nuevo se ve así).
    await user.click(toggle);
    expect(await within(dialog).findByRole('textbox', { name: 'Tope de niveles en Markdown' })).toHaveValue(
      '2',
    );
    await user.type(within(dialog).getByRole('textbox', { name: 'Tope de niveles en Markdown' }), '9');
    await user.click(toggle);
    await user.click(within(dialog).getByRole('button', { name: 'Lanzar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')).toHaveLength(1));
    const body = (await callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')[0]?.json()) as {
      params: Record<string, unknown>;
    };
    expect(body.params).not.toHaveProperty('markdown_diagram_depth');
  });

  it('quita la documentación anterior elegida si deja de ser comparable', async () => {
    stubEventSource();
    stubApi(
      routes([
        previousRun('01JPREV0000000000000000001', { connection: 'ventas', schema: null, markdown: true }),
      ]),
    );
    const { user, dialog } = await openForm();

    await user.click(within(dialog).getByRole('switch', { name: /^Markdown/ }));
    const previous = await within(dialog).findByRole('combobox', { name: 'Comparar con la documentación' });
    await waitFor(() => expect(within(previous).getAllByRole('option')).toHaveLength(2));
    await user.selectOptions(previous, '01JPREV0000000000000000001');
    expect(previous).toHaveValue('01JPREV0000000000000000001');
    await user.type(within(dialog).getByRole('textbox', { name: 'Schema' }), 'OTRO');

    await waitFor(() => expect(previous).toHaveValue(''));
    expect(within(previous).getAllByRole('option')).toHaveLength(1);
  });
});

describe('resultados de la documentación Markdown', () => {
  it('explica la carpeta y abre los cambios en el visor de diferencias, sin evolución', async () => {
    stubEventSource();
    const fetchMock = stubApi({
      ...session(ADMIN),
      [`GET /api/v1/runs/${RUN_ID}`]: { body: MARKDOWN_RUN },
      [`GET /api/v1/runs/${RUN_ID}/diff`]: { body: SCHEMA_DIFF },
      [`GET /api/v1/runs/${RUN_ID}/artifacts/61/preview`]: { text: '# Portada' },
    });

    renderRoute(`/runs/${RUN_ID}`);

    expect(await screen.findByRole('heading', { name: 'Markdown' })).toBeInTheDocument();
    expect(
      await screen.findByRole('heading', { name: 'Cambios respecto de la documentación anterior' }),
    ).toBeInTheDocument();
    expect(await screen.findByRole('tab', { name: 'Tablas (3)' })).toBeInTheDocument();
    expect(screen.queryByText('Comparar con otra ejecución')).not.toBeInTheDocument();
    expect(callsTo(fetchMock, 'GET', `/api/v1/runs/${RUN_ID}/diff`)).toHaveLength(1);
  });
});

describe('stripFrontMatter', () => {
  it('quita el front matter JSON de una página', () => {
    expect(stripFrontMatter('---\n{"id": "table:main.a"}\n---\n# a\n')).toBe('# a\n');
    expect(stripFrontMatter('---\r\n{}\r\n---\r\n# a')).toBe('# a');
  });

  it('no toca una página sin front matter ni una regla en medio', () => {
    const text = '# a\n\n---\n\ntexto\n---\n';
    expect(stripFrontMatter(text)).toBe(text);
  });
});
