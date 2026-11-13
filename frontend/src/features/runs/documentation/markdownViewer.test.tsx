import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ADMIN, session, stubApi } from '../../../test/api';
import { stubEventSource } from '../../../test/eventSource';
import { DOC_RUN, RUN_ID } from '../../../test/fixtures_runs';
import { renderRoute } from '../../../test/render';
import type { Artifact, RunDetail } from '../useRuns';
import { BRIDGE_SCRIPT, BRIDGE_SHA256 } from './markdownFrame';
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
  // DDL como lo escribe util_bbdd (```sql), con un nombre hostil: se resalta y se escapa.
  101:
    '# Portada\n\n[Tablas](tables/index.md) · [Catálogo](catalog.json)\n\n' +
    '```sql\nCREATE TABLE "</code><script>x()</script>" (id INTEGER);\n```',
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
  it('abre la portada en un iframe con scripts, origen opaco y el puente autorizado por su hash', async () => {
    const { index } = await openViewer();

    expect(index).toHaveAttribute('sandbox', 'allow-scripts');
    expect(index.getAttribute('sandbox')).not.toContain('allow-same-origin');
    const srcdoc = index.getAttribute('srcdoc') ?? '';
    expect(srcdoc).toContain('<h1>Portada</h1>');
    expect(srcdoc).toContain(`script-src 'sha256-${BRIDGE_SHA256}'`);
    expect(srcdoc).toContain(`<script>${BRIDGE_SCRIPT}</script>`);
    expect(srcdoc).toContain(`data-ubw-parent="${window.location.origin}"`);
  });

  it('resalta el DDL (```sql) sin dejar pasar marcado y da al puente los textos de «Copiar»', async () => {
    const { index } = await openViewer();

    // El puente copia dentro del iframe: necesita el permiso delegado (la SPA no puede, el foco es del iframe).
    expect(index).toHaveAttribute('allow', 'clipboard-write');
    await waitFor(() => expect(index.getAttribute('srcdoc')).toContain('class="hljs-keyword"'));
    const srcdoc = index.getAttribute('srcdoc') ?? '';
    expect(srcdoc).toContain('&lt;/code&gt;&lt;script&gt;x()&lt;/script&gt;');
    expect(srcdoc.match(/<script/g)).toHaveLength(1); // solo el puente
    expect(srcdoc).toContain('data-ubw-copy="Copiar"');
    expect(srcdoc).toContain('data-ubw-copied="Copiado"');
    expect(srcdoc).toContain('data-ubw-copy-failed="No se pudo copiar; selecciona el texto"');
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
    await user.click(within(tree).getByRole('button', { name: /views\/v_pedidos\.md/ }));
    await waitFor(() => expect(frame('views/v_pedidos.md')).toBeInTheDocument());
  });

  it('con el índice de util_bbdd 5.4.0 muestra los nombres reales y busca por ellos', async () => {
    stubEventSource();
    stubApi({
      ...routes(),
      [`GET /api/v1/runs/${RUN_ID}/markdown-pages`]: {
        body: {
          source: 'manifest',
          pages: [
            { path: 'index.md', title: 'Portada TIENDA', section: 'home', role: 'home', artifact_id: 101 },
            { path: 'tables/index.md', title: 'Tablas', section: 'tables', role: 'index', artifact_id: 102 },
            {
              path: 'tables/pedidos.md',
              title: 'Tabla: PEDIDOS_<b>2024</b>',
              section: 'tables',
              role: 'object',
              kind: 'table',
              artifact_id: 103,
            },
            {
              path: 'views/v_pedidos.md',
              title: 'Vista: V_PEDIDOS',
              section: 'views',
              role: 'object',
              artifact_id: 104,
            },
          ],
        },
      },
    });
    const user = userEvent.setup();
    renderRoute(`/runs/${RUN_ID}`);
    const tree = await screen.findByRole('navigation', { name: 'Páginas de la documentación Markdown' });

    await user.type(within(tree).getByRole('textbox', { name: 'Buscar página' }), 'PEDIDOS_<b>');
    // El título viene de la BD: se pinta como texto, sin interpretar el HTML.
    const result = within(tree).getByRole('button', { name: /PEDIDOS_<b>2024<\/b>/ });
    expect(within(tree).queryByText('2024', { selector: 'b' })).not.toBeInTheDocument();
    await user.click(result);
    await waitFor(() => expect(frame('tables/pedidos.md')).toBeInTheDocument());
    await user.clear(within(tree).getByRole('textbox', { name: 'Buscar página' }));
    await user.selectOptions(within(tree).getByRole('combobox', { name: 'Sección' }), 'views');
    expect(within(tree).getByRole('button', { name: 'V_PEDIDOS' })).toBeInTheDocument();
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
