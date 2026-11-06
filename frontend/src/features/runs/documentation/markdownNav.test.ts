import { describe, expect, it } from 'vitest';

import type { Artifact } from '../useRuns';
import { buildFrameDocument, frameCsp, navHref, sanitizeMarkdownHtml } from './markdownFrame';
import {
  DOCS_ROOT,
  buildPages,
  initialOf,
  objectName,
  pagesFromIndex,
  parseLocation,
  resolveLink,
} from './markdownNav';

let nextId = 1;
const doc = (path: string, previewable = path.endsWith('.md')): Artifact => ({
  id: nextId++,
  path: `${DOCS_ROOT}${path}`,
  kind: 'markdown',
  mime: 'text/markdown',
  size_bytes: 10,
  sha256: 'c'.repeat(64),
  created_at: '2026-11-06T08:00:00Z',
  previewable,
});

const ARTIFACTS = [
  doc('index.md'),
  doc('changes.md'),
  doc('traceability.md'),
  doc('tables/index.md'),
  doc('tables/index-p.md'),
  doc('tables/pedidos.md'),
  doc('tables/clientes.md'),
  doc('views/v_pedidos.md'),
  doc('database/info.md'),
  doc('catalog.json', false),
  doc('llms-full.txt', false),
  doc('assets/javascripts/mermaid.min.js', false),
  { ...doc('x.md'), path: 'outputs/markdown/documentacion/mkdocs.md' }, // fuera de docs/
];

describe('buildPages', () => {
  it('ordena portada, secciones (índices y objetos), base de datos, trazabilidad y cambios', () => {
    expect(buildPages(ARTIFACTS).map((p) => [p.section, p.path, p.role])).toEqual([
      ['root', 'index.md', 'object'],
      ['tables', 'tables/index.md', 'index'],
      ['tables', 'tables/index-p.md', 'letter'],
      ['tables', 'tables/clientes.md', 'object'],
      ['tables', 'tables/pedidos.md', 'object'],
      ['views', 'views/v_pedidos.md', 'object'],
      ['database', 'database/info.md', 'object'],
      ['traceability', 'traceability.md', 'object'],
      ['changes', 'changes.md', 'object'],
    ]);
  });

  it('agrupa por letra inicial', () => {
    const pages = buildPages(ARTIFACTS);
    expect(pages.filter((p) => p.section === 'tables' && p.role === 'object').map(initialOf)).toEqual([
      'C',
      'P',
    ]);
  });
});

describe('pagesFromIndex (util_bbdd 5.4.0, G51)', () => {
  const byPath = (path: string) => {
    const artifact = ARTIFACTS.find((a) => a.path === `${DOCS_ROOT}${path}`);
    if (!artifact) throw new Error(path);
    return artifact;
  };
  const entry = (path: string, title: string, section: string, role: string, extra = {}) => ({
    path,
    title,
    section,
    role: role as 'home' | 'index' | 'letter' | 'object' | 'page',
    artifact_id: byPath(path).id,
    letter: null,
    kind: null,
    ...extra,
  });
  const INDEX = [
    entry('index.md', 'Documentación de la Base de Datos - TIENDA', 'home', 'home'),
    entry('tables/index.md', 'Tablas', 'tables', 'index'),
    entry('tables/index-p.md', 'Tablas · P', 'tables', 'letter', { letter: 'p' }),
    entry('tables/pedidos.md', 'Tabla: PEDIDOS_2024', 'tables', 'object', { kind: 'table' }),
    entry('tables/clientes.md', 'Tabla: clientes', 'tables', 'object', { kind: 'table' }),
    entry('traceability.md', 'Trazabilidad', 'traceability', 'page'),
    entry('database/info.md', 'Información de la Base de Datos', 'database', 'page'),
  ];

  it('respeta el orden de util_bbdd dentro de cada sección y usa los títulos', () => {
    const pages = pagesFromIndex(INDEX, ARTIFACTS);
    expect(pages.map((p) => [p.section, p.path, p.role])).toEqual([
      ['root', 'index.md', 'object'],
      ['tables', 'tables/index.md', 'index'],
      ['tables', 'tables/index-p.md', 'letter'],
      ['tables', 'tables/pedidos.md', 'object'],
      ['tables', 'tables/clientes.md', 'object'],
      ['database', 'database/info.md', 'object'],
      ['traceability', 'traceability.md', 'object'],
    ]);
    expect(pages.map(objectName)).toEqual([
      'Documentación de la Base de Datos - TIENDA',
      'Tablas',
      'Tablas · P',
      'PEDIDOS_2024',
      'clientes',
      'Información de la Base de Datos',
      'Trazabilidad',
    ]);
    expect(pages.filter((p) => p.role === 'object' && p.section === 'tables').map(initialOf)).toEqual([
      'P',
      'C',
    ]);
  });

  it('descarta entradas cuyo artefacto no cuadra con la ruta o no es una página', () => {
    const catalog = byPath('catalog.json');
    const pages = pagesFromIndex(
      [
        { ...entry('index.md', 'x', 'home', 'home'), artifact_id: byPath('tables/pedidos.md').id },
        { ...entry('index.md', 'x', 'home', 'home'), path: 'catalog.json', artifact_id: catalog.id },
        { ...entry('index.md', 'x', 'home', 'home'), artifact_id: 999_999 },
      ],
      ARTIFACTS,
    );
    expect(pages).toEqual([]);
  });

  it('sin título usa el slug', () => {
    expect(buildPages(ARTIFACTS).map(objectName)).toContain('pedidos');
  });
});

describe('resolveLink', () => {
  it('resuelve rutas relativas, ../ y anclas entre páginas registradas', () => {
    expect(resolveLink('tables/pedidos.md', 'clientes.md', ARTIFACTS)).toEqual({
      type: 'page',
      path: 'tables/clientes.md',
      hash: '',
    });
    expect(resolveLink('tables/pedidos.md', '../views/v_pedidos.md#col-id', ARTIFACTS)).toEqual({
      type: 'page',
      path: 'views/v_pedidos.md',
      hash: 'col-id',
    });
    expect(resolveLink('index.md', './tables/index.md', ARTIFACTS)).toMatchObject({
      path: 'tables/index.md',
    });
    expect(resolveLink('tables/pedidos.md', '#col-total', ARTIFACTS)).toEqual({
      type: 'page',
      path: 'tables/pedidos.md',
      hash: 'col-total',
    });
    expect(resolveLink('index.md', 'tables/pedid%6Fs.md', ARTIFACTS)).toMatchObject({
      path: 'tables/pedidos.md',
    });
  });

  it('ofrece la descarga de lo que no es una página', () => {
    const target = resolveLink('index.md', 'catalog.json', ARTIFACTS);
    expect(target.type).toBe('download');
    expect(target.type === 'download' && target.artifact.path).toBe(`${DOCS_ROOT}catalog.json`);
  });

  it('no sale de docs/ ni acepta ficheros no registrados', () => {
    expect(resolveLink('index.md', '../mkdocs.md', ARTIFACTS).type).toBe('missing');
    expect(resolveLink('tables/pedidos.md', '../../../../run.json', ARTIFACTS).type).toBe('missing');
    expect(resolveLink('tables/pedidos.md', 'no-existe.md', ARTIFACTS).type).toBe('missing');
    expect(resolveLink('index.md', '%E0%A4%A.md', ARTIFACTS).type).toBe('missing');
    expect(resolveLink('index.md', 'tables\\pedidos.md', ARTIFACTS).type).toBe('missing');
  });

  it('solo abre fuera http y https; el resto de esquemas y rutas absolutas se ignoran (D4)', () => {
    expect(resolveLink('index.md', 'https://example.com/a?b=1', ARTIFACTS)).toEqual({
      type: 'external',
      url: 'https://example.com/a?b=1',
    });
    expect(resolveLink('index.md', 'http://example.com', ARTIFACTS).type).toBe('external');
    for (const href of [
      'javascript:alert(1)',
      ' JavaScript:alert(1)',
      'data:text/html,<script>alert(1)</script>',
      'file:///etc/passwd',
      'vbscript:x',
      '//evil.example/x',
      '/api/v1/runs',
      '',
      'a'.repeat(3000),
    ]) {
      expect(resolveLink('index.md', href, ARTIFACTS).type, href).toBe('ignored');
    }
  });
});

describe('parseLocation', () => {
  it('separa la página y el ancla', () => {
    expect(parseLocation('tables/pedidos.md#col-id')).toEqual({ path: 'tables/pedidos.md', hash: 'col-id' });
    expect(parseLocation('index.md')).toEqual({ path: 'index.md', hash: '' });
    expect(parseLocation(null)).toBeNull();
  });
});

describe('documento del iframe', () => {
  it('quita scripts, manejadores y esquemas peligrosos, y conserva anclas, SVG y etiquetas de Mermaid', () => {
    const html = sanitizeMarkdownHtml(
      '<p><a id="col-id"></a><a href="pedidos.md">pedidos</a><a href="javascript:alert(1)">x</a></p>' +
        '<img src="x" onerror="alert(1)"><script>alert(2)</script><iframe src="https://e"></iframe>' +
        '<form action="https://e"><input></form>' +
        '<svg><style>.a{fill:red}</style><g class="a"><rect width="1" height="1"></rect></g>' +
        '<foreignObject><div><span class="nodeLabel">PEDIDOS</span><img src=x onerror=alert(3)></div></foreignObject></svg>',
    );
    expect(html).toContain('<a id="col-id"></a>');
    expect(html).toContain('<a href="pedidos.md">pedidos</a>');
    expect(html).toContain('PEDIDOS');
    expect(html).toContain('<style>');
    expect(html).toContain('<rect');
    expect(html).not.toMatch(/onerror|<script|<iframe|<form|javascript:/i);
  });

  it('el script del puente lleva el nonce de la CSP, escapa el ancla y solo habla con el origen de la SPA', () => {
    const page = buildFrameDocument(
      '<p>x</p>',
      'abc123',
      '</script><script>alert(1)//',
      'https://ubw.example',
    );
    expect(page).toContain(`content="${frameCsp('abc123')}"`);
    expect(frameCsp('abc123')).toContain("script-src 'nonce-abc123'");
    expect(frameCsp('abc123')).toContain("connect-src 'none'");
    expect(page.match(/<script/g)).toHaveLength(1);
    expect(page).toContain('<script nonce="abc123">');
    expect(page).not.toContain('</script><script>alert');
    expect(page).toContain('"https://ubw.example"');
  });

  it('acepta solo mensajes del puente con el formato esperado (T5)', () => {
    expect(navHref({ type: 'ubw-md-nav', href: 'a.md' })).toBe('a.md');
    expect(navHref({ type: 'otro', href: 'a.md' })).toBeNull();
    expect(navHref({ type: 'ubw-md-nav', href: 3 })).toBeNull();
    expect(navHref({ type: 'ubw-md-nav', href: 'a'.repeat(3000) })).toBeNull();
    expect(navHref('ubw-md-nav')).toBeNull();
    expect(navHref(null)).toBeNull();
  });
});
