import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ADMIN, session, stubApi } from '../../../test/api';
import { stubEventSource } from '../../../test/eventSource';
import { DOC_RUN, RUN_ID } from '../../../test/fixtures_runs';
import { renderRoute } from '../../../test/render';
import type { Artifact, RunDetail } from '../useRuns';
import { DOCS_ROOT } from './markdownNav';

const md = (id: number, path: string, previewable = path.endsWith('.md')): Artifact => ({
  id,
  path: `${DOCS_ROOT}${path}`,
  kind: 'markdown',
  mime: 'text/markdown',
  size_bytes: 100,
  sha256: 'c'.repeat(64),
  created_at: '2026-11-06T08:00:00Z',
  previewable,
});

/** 45 tablas (paginadas por letra: más de 40), una vista y los auxiliares. */
const TABLES = Array.from({ length: 45 }, (_, i) => md(200 + i, `tables/${i < 30 ? 'a' : 'p'}tabla${i}.md`));
const RUN: RunDetail = {
  ...DOC_RUN,
  params: { connection: 'origen', word: false, excel: false, html: false, markdown: true },
  site_url: null,
  artifacts: [
    md(101, 'index.md'),
    md(102, 'tables/index.md'),
    md(103, 'tables/pedidos.md'),
    md(104, 'views/v_pedidos.md'),
    md(105, 'catalog.json'),
    ...TABLES,
  ],
};

const PAGES: Record<number, string> = {
  101: '# Portada\n\n[Tablas](tables/index.md) · [Catálogo](catalog.json)',
  102: '# Tablas\n\n[pedidos](pedidos.md)',
  103: '---\n{"id": "t"}\n---\n# Tabla: PEDIDOS\n\n| <a id="col-id"></a>ID |\n|---|\n\n[vista](../views/v_pedidos.md#col-id)',
  104: '# Vista: V_PEDIDOS',
};

function routes() {
  const handlers: Parameters<typeof stubApi>[0] = {
    ...session(ADMIN),
    [`GET /api/v1/runs/${RUN_ID}`]: { body: RUN },
  };
  for (const [id, text] of Object.entries(PAGES)) {
    handlers[`GET /api/v1/runs/${RUN_ID}/artifacts/${id}/preview`] = { text };
  }
  return handlers;
}

function frame(path: string): HTMLIFrameElement {
  return screen.getByTitle(`Página Markdown ${path}`) as HTMLIFrameElement;
}

/** Simula el `postMessage` del puente desde el iframe (o desde otra ventana con `source`). */
function postFromFrame(href: string, source: Window | null) {
  act(() => {
    window.dispatchEvent(new MessageEvent('message', { data: { type: 'ubw-md-nav', href }, source }));
  });
}

async function openViewer() {
  stubEventSource();
  stubApi(routes());
  const user = userEvent.setup();
  renderRoute(`/runs/${RUN_ID}`);
  const index = await screen.findByTitle('Página Markdown index.md');
  return { user, index: index as HTMLIFrameElement };
}

afterEach(() => vi.restoreAllMocks());

describe('visor de la documentación Markdown', () => {
  it('abre la portada en un iframe con scripts, origen opaco y CSP con nonce', async () => {
    const { index } = await openViewer();

    expect(index).toHaveAttribute('sandbox', 'allow-scripts');
    expect(index.getAttribute('sandbox')).not.toContain('allow-same-origin');
    const srcdoc = index.getAttribute('srcdoc') ?? '';
    expect(srcdoc).toContain('<h1>Portada</h1>');
    const nonce = /script-src 'nonce-([0-9a-f]{32})'/.exec(srcdoc)?.[1];
    expect(nonce).toBeDefined();
    expect(srcdoc).toContain(`<script nonce="${nonce}">`);
  });

  it('navega por los enlaces del puente, con anclas, atrás y adelante, y lo refleja en ?md=', async () => {
    const { user, index } = await openViewer();

    postFromFrame('tables/index.md', index.contentWindow);
    await waitFor(() => expect(frame('tables/index.md')).toBeInTheDocument());
    postFromFrame('pedidos.md', frame('tables/index.md').contentWindow);
    await waitFor(() =>
      expect(frame('tables/pedidos.md').getAttribute('srcdoc')).toContain('Tabla: PEDIDOS'),
    );
    // El front matter no se pinta; el ancla de la columna se conserva.
    expect(frame('tables/pedidos.md').getAttribute('srcdoc')).not.toContain('&quot;id&quot;');
    expect(frame('tables/pedidos.md').getAttribute('srcdoc')).toContain('id="col-id"');

    postFromFrame('../views/v_pedidos.md#col-id', frame('tables/pedidos.md').contentWindow);
    await waitFor(() => expect(screen.getByText('views/v_pedidos.md#col-id')).toBeInTheDocument());
    await waitFor(() => expect(frame('views/v_pedidos.md').getAttribute('srcdoc')).toContain('"col-id"'));

    await user.click(screen.getByRole('button', { name: 'Página anterior' }));
    await waitFor(() => expect(frame('tables/pedidos.md')).toBeInTheDocument());
    await user.click(screen.getByRole('button', { name: 'Página anterior' }));
    await user.click(screen.getByRole('button', { name: 'Página siguiente' }));
    await waitFor(() => expect(frame('tables/pedidos.md')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: 'Página siguiente' })).toBeEnabled();
  });

  it('ignora los mensajes que no vienen del iframe del visor (T5)', async () => {
    await openViewer();

    postFromFrame('tables/index.md', window);
    postFromFrame('tables/index.md', null);

    expect(screen.getByTitle('Página Markdown index.md')).toBeInTheDocument();
    expect(screen.queryByTitle('Página Markdown tables/index.md')).not.toBeInTheDocument();
  });

  it('ofrece la descarga de un fichero sin vista previa y avisa de un enlace roto', async () => {
    const { index } = await openViewer();

    postFromFrame('catalog.json', index.contentWindow);
    const notice = await screen.findByRole('alert', {
      name: 'El enlace apunta a un fichero sin vista previa',
    });
    expect(within(notice).getByRole('link', { name: 'Descargar catalog.json' })).toHaveAttribute(
      'href',
      `/api/v1/runs/${RUN_ID}/artifacts/105`,
    );

    postFromFrame('../../run.json', index.contentWindow);
    expect(
      await screen.findByText('El enlace apunta a una página que no está en esta documentación'),
    ).toBeInTheDocument();
    expect(screen.getByText('../../run.json')).toBeInTheDocument();
  });

  it('pide confirmación antes de abrir un enlace externo y nunca abre otros esquemas (D4)', async () => {
    const opened = vi.spyOn(window, 'open').mockReturnValue(null);
    const { user, index } = await openViewer();

    for (const href of [
      'javascript:alert(1)',
      'data:text/html,x',
      'file:///etc/passwd',
      '//evil.example/x',
    ]) {
      postFromFrame(href, index.contentWindow);
    }
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    postFromFrame('https://example.com/req/1', index.contentWindow);
    const dialog = await screen.findByRole('dialog', { name: 'Vas a salir de la aplicación' });
    expect(within(dialog).getByText('https://example.com/req/1')).toBeInTheDocument();
    expect(opened).not.toHaveBeenCalled();
    await user.click(within(dialog).getByRole('button', { name: 'Abrir en otra pestaña' }));
    expect(opened).toHaveBeenCalledWith('https://example.com/req/1', '_blank', 'noopener,noreferrer');
  });

  it('busca páginas, pagina por letra las secciones grandes y abre desde el árbol', async () => {
    const { user } = await openViewer();
    const tree = screen.getByRole('navigation', { name: 'Páginas de la documentación Markdown' });

    await user.selectOptions(within(tree).getByRole('combobox', { name: 'Sección' }), 'tables');
    const letters = within(tree).getByRole('group', { name: 'Letra inicial' });
    expect(within(letters).getByRole('button', { name: 'A' })).toHaveAttribute('aria-pressed', 'true');
    expect(within(tree).getAllByRole('listitem')).toHaveLength(31); // índice + 30 que empiezan por «a»
    await user.click(within(letters).getByRole('button', { name: 'P' }));
    expect(within(tree).getByRole('button', { name: 'pedidos' })).toBeInTheDocument();

    await user.type(within(tree).getByRole('textbox', { name: 'Buscar página' }), 'v_ped');
    expect(within(tree).getByText('1 página encontrada')).toBeInTheDocument();
    await user.click(within(tree).getByRole('button', { name: 'views/v_pedidos.md' }));
    await waitFor(() => expect(frame('views/v_pedidos.md')).toBeInTheDocument());
  });

  it('abre la página de ?md= (enlace compartible)', async () => {
    stubEventSource();
    stubApi(routes());

    renderRoute(`/runs/${RUN_ID}?md=${encodeURIComponent('tables/pedidos.md#col-id')}`);

    const page = await screen.findByTitle('Página Markdown tables/pedidos.md');
    await waitFor(() => expect(page.getAttribute('srcdoc')).toContain('Tabla: PEDIDOS'));
    expect(screen.getByText('tables/pedidos.md#col-id')).toBeInTheDocument();
    fireEvent.load(page);
  });
});
