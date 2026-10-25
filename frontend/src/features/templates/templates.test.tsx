import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi, USER } from '../../test/api';
import { stubEventSource } from '../../test/eventSource';
import { DOC_RUN, DOCUMENTATION, ORACLE_CONNECTION, PROJECT, RUN, RUN_ID } from '../../test/fixtures_runs';
import { renderRoute } from '../../test/render';
import type { Operation } from '../runs/useRuns';
import type { DocumentTemplate } from './useTemplates';

const OWN: DocumentTemplate = {
  id: '01JTEMPLATEPR0JECT00000000',
  scope: 'project',
  kind: 'word',
  name: 'Corporativa',
  filename: 'corporativa.docx',
  size_bytes: 20480,
  sha256: 'a'.repeat(64),
  table_style: 'Table Grid',
  table_styles: ['Light Grid Accent 1', 'Table Grid'],
  username: 'admin',
  created_at: '2026-10-25T08:00:00Z',
  updated_at: '2026-10-25T08:00:00Z',
};

const GLOBAL: DocumentTemplate = {
  ...OWN,
  id: '01JTEMPLATEGL0BAL000000000',
  scope: 'global',
  kind: 'excel',
  name: 'Marca',
  filename: 'marca.xlsx',
  table_style: 'TableStyleMedium2',
  table_styles: ['TableStyleLight1', 'TableStyleMedium2'],
};

const PROJECT_URL = '/api/v1/projects/5/document-templates';

function stubProject(me: object, role: string, templates: DocumentTemplate[] | 'error' = [OWN, GLOBAL]) {
  let current = templates === 'error' ? [] : templates;
  return stubApi({
    ...session(me),
    'GET /api/v1/projects/5': { body: { ...PROJECT, my_role: role } },
    'GET /api/v1/projects/5/runs': { body: { items: [], total: 0 } },
    [`GET ${PROJECT_URL}`]: () =>
      templates === 'error'
        ? { status: 500, body: { title: 'Error interno', status: 500 } }
        : { body: current },
    [`POST ${PROJECT_URL}`]: () => {
      current = [OWN, ...current];
      return { status: 201, body: OWN };
    },
    [`PATCH ${PROJECT_URL}/${OWN.id}`]: { body: { ...OWN, table_style: 'Light Grid Accent 1' } },
    [`DELETE ${PROJECT_URL}/${OWN.id}`]: () => {
      current = current.filter((t) => t.id !== OWN.id);
      return { status: 204 };
    },
  });
}

async function openTab(user: ReturnType<typeof userEvent.setup>) {
  renderRoute('/projects/5');
  await user.click(await screen.findByRole('tab', { name: 'Plantillas' }));
}

describe('pestaña Plantillas del proyecto', () => {
  it('sube una plantilla como multipart con su nombre', async () => {
    const fetchMock = stubProject(ADMIN, 'editor', []);
    const user = userEvent.setup();

    await openTab(user);
    expect(await screen.findByText('Todavía no hay plantillas.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Word base' })).toHaveAttribute(
      'href',
      '/api/v1/document-templates/base/word',
    );
    const input = document.querySelector<HTMLInputElement>('input[type="file"]');
    await user.upload(input as HTMLInputElement, new File(['PK'], 'corporativa.docx'));
    await user.type(screen.getByRole('textbox', { name: /Nombre/ }), 'Corporativa');
    await user.click(screen.getByRole('button', { name: 'Subir' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', PROJECT_URL)).toHaveLength(1));
    const request = callsTo(fetchMock, 'POST', PROJECT_URL)[0] as Request;
    expect(request.headers.get('Content-Type')).toMatch(/^multipart\/form-data/);
    expect(await screen.findByRole('table', { name: 'Plantillas de documento' })).toBeInTheDocument();
  });

  it('las globales se ven y se descargan, pero solo se gestionan las del proyecto', async () => {
    const fetchMock = stubProject(ADMIN, 'editor');
    const user = userEvent.setup();

    await openTab(user);
    const table = await screen.findByRole('table', { name: 'Plantillas de documento' });
    expect(within(table).getByText('Global')).toBeInTheDocument();
    expect(within(table).getByRole('link', { name: 'Descargar Marca' })).toHaveAttribute(
      'href',
      `${PROJECT_URL}/${GLOBAL.id}/file`,
    );
    expect(within(table).queryByRole('button', { name: 'Borrar Marca' })).not.toBeInTheDocument();
    expect(
      within(table).queryByRole('combobox', { name: 'Estilo de tabla de Marca' }),
    ).not.toBeInTheDocument();

    await user.selectOptions(
      within(table).getByRole('combobox', { name: 'Estilo de tabla de Corporativa' }),
      'Light Grid Accent 1',
    );
    await waitFor(() => expect(callsTo(fetchMock, 'PATCH', `${PROJECT_URL}/${OWN.id}`)).toHaveLength(1));
    expect(await callsTo(fetchMock, 'PATCH', `${PROJECT_URL}/${OWN.id}`)[0]?.json()).toEqual({
      table_style: 'Light Grid Accent 1',
    });

    await user.click(within(table).getByRole('button', { name: 'Borrar Corporativa' }));
    const dialog = await screen.findByRole('dialog', { name: 'Borrar plantilla' });
    await user.click(within(dialog).getByRole('button', { name: 'Borrar' }));
    await waitFor(() => expect(callsTo(fetchMock, 'DELETE', `${PROJECT_URL}/${OWN.id}`)).toHaveLength(1));
    await waitFor(() => expect(screen.queryByText('Corporativa')).not.toBeInTheDocument());
  });

  it('una plantilla sin estilo de tabla elegido lo muestra como «Por defecto»', async () => {
    stubProject(ADMIN, 'editor', [{ ...OWN, table_style: null }]);
    const user = userEvent.setup();

    await openTab(user);
    const select = await screen.findByRole('combobox', { name: 'Estilo de tabla de Corporativa' });
    expect(select).toHaveValue('');
    expect(within(select).getByRole('option', { name: 'Por defecto' })).toBeInTheDocument();
  });

  it('una plantilla con estilo elegido puede volver a «Por defecto»', async () => {
    const fetchMock = stubProject(ADMIN, 'editor', [{ ...OWN, table_style: 'Normal Table' }]);
    const user = userEvent.setup();

    await openTab(user);
    const select = await screen.findByRole('combobox', { name: 'Estilo de tabla de Corporativa' });
    await user.selectOptions(select, 'Por defecto');

    await waitFor(() => expect(callsTo(fetchMock, 'PATCH', `${PROJECT_URL}/${OWN.id}`)).toHaveLength(1));
    expect(await callsTo(fetchMock, 'PATCH', `${PROJECT_URL}/${OWN.id}`)[0]?.json()).toEqual({
      table_style: null,
    });
  });

  it('un lector solo consulta y descarga', async () => {
    stubProject(USER, 'viewer');
    const user = userEvent.setup();

    await openTab(user);
    expect(
      await screen.findByText('Solo los editores del proyecto pueden subir, cambiar o borrar plantillas.'),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Subir' })).not.toBeInTheDocument();
    expect(await screen.findByRole('link', { name: 'Descargar Corporativa' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Borrar Corporativa' })).not.toBeInTheDocument();
  });

  it('muestra el error si no se pueden cargar', async () => {
    stubProject(ADMIN, 'owner', 'error');
    const user = userEvent.setup();

    await openTab(user);
    expect(await screen.findByText('Error interno')).toBeInTheDocument();
  });
});

describe('catálogo global (admin)', () => {
  it('lista y sube plantillas globales', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/document-templates': { body: [GLOBAL] },
      'POST /api/v1/admin/document-templates': { status: 201, body: GLOBAL },
    });
    const user = userEvent.setup();

    renderRoute('/admin/templates');
    expect(await screen.findByRole('heading', { name: 'Plantillas de documento' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Borrar Marca' })).toBeInTheDocument();
    const input = document.querySelector<HTMLInputElement>('input[type="file"]');
    await user.upload(input as HTMLInputElement, new File(['PK'], 'marca.xltx'));
    await user.click(screen.getByRole('button', { name: 'Subir' }));

    await waitFor(() =>
      expect(callsTo(fetchMock, 'POST', '/api/v1/admin/document-templates')).toHaveLength(1),
    );
    const request = callsTo(fetchMock, 'POST', '/api/v1/admin/document-templates')[0] as Request;
    expect(request.headers.get('Content-Type')).toMatch(/^multipart\/form-data/);
  });
});

const templateParam = (name: string, kind: 'word' | 'excel'): Operation['params'][number] => ({
  name,
  type: 'template',
  template_kind: kind,
  required: false,
  default: null,
  description: name,
  minimum: null,
  maximum: null,
  options: null,
  group: 'templates',
});

const WITH_TEMPLATES: Operation = {
  ...DOCUMENTATION,
  params: [
    ...DOCUMENTATION.params,
    { ...(DOCUMENTATION.params[2] as Operation['params'][number]), name: 'excel' },
    templateParam('word_template', 'word'),
    templateParam('excel_template', 'excel'),
  ],
};

describe('plantillas al lanzar la documentación', () => {
  it('ofrece las plantillas de cada formato y descarta la de un formato desmarcado', async () => {
    stubEventSource();
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/projects/5': { body: PROJECT },
      'GET /api/v1/projects/5/runs': { body: { items: [], total: 0 } },
      'GET /api/v1/projects/5/connections': { body: [ORACLE_CONNECTION] },
      'GET /api/v1/operations': { body: [WITH_TEMPLATES] },
      [`GET ${PROJECT_URL}`]: { body: [OWN, GLOBAL] },
      'POST /api/v1/projects/5/runs': { status: 202, body: { ...RUN, status: 'queued' } },
      [`GET /api/v1/runs/${RUN_ID}`]: { body: { ...DOC_RUN, status: 'queued', artifacts: [] } },
    });
    const user = userEvent.setup();

    renderRoute('/projects/5');
    await user.click(await screen.findByRole('button', { name: 'Lanzar ejecución' }));
    const dialog = await screen.findByRole('dialog');
    await user.selectOptions(await within(dialog).findByRole('combobox', { name: 'Conexión' }), 'ventas');
    const word = await within(dialog).findByRole('combobox', { name: 'Plantilla Word' });
    expect(
      within(word).getByRole('option', { name: 'Sin plantilla (formato por defecto)' }),
    ).toBeInTheDocument();
    expect(within(word).getByRole('option', { name: 'Corporativa' })).toBeInTheDocument();
    expect(within(word).queryByRole('option', { name: 'Marca' })).not.toBeInTheDocument();
    const excel = within(dialog).getByRole('combobox', { name: 'Plantilla Excel' });
    expect(within(excel).getByRole('group', { name: 'Globales' })).toBeInTheDocument();
    await user.selectOptions(word, OWN.id);
    await user.selectOptions(excel, GLOBAL.id);

    await user.click(within(dialog).getByRole('switch', { name: /^Excel/ }));
    expect(within(dialog).queryByRole('combobox', { name: 'Plantilla Excel' })).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Lanzar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')).toHaveLength(1));
    const body = (await callsTo(fetchMock, 'POST', '/api/v1/projects/5/runs')[0]?.json()) as {
      params: Record<string, unknown>;
    };
    expect(body.params).toMatchObject({ excel: false, word_template: OWN.id, excel_template: null });
  });
});

describe('avisos de una ejecución', () => {
  it('muestra las plantillas que no se pudieron aplicar', async () => {
    stubEventSource();
    const warning = 'La plantilla Word no se pudo aplicar: el documento Word usa el formato por defecto.';
    stubApi({
      ...session(ADMIN),
      [`GET /api/v1/runs/${RUN_ID}`]: { body: { ...DOC_RUN, warnings: [warning] } },
    });

    renderRoute(`/runs/${RUN_ID}`);

    expect(await screen.findByText('La ejecución terminó con avisos')).toBeInTheDocument();
    expect(screen.getByText(warning)).toBeInTheDocument();
  });
});
