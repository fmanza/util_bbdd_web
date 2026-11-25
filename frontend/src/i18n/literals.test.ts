import ts from 'typescript';
import { describe, expect, it } from 'vitest';

import core from './es/core.json';
import features from './es/features.json';

/**
 * Requisito i18n (`frontend.instructions.md`): ningún texto visible escrito a mano en el código y ninguna clave `t()`
 * que no exista. Recorre el AST de las fuentes (no de los tests) con el compilador de TypeScript del proyecto.
 */

const SOURCES = import.meta.glob<string>(
  ['/src/**/*.{ts,tsx}', '!/src/**/*.test.{ts,tsx}', '!/src/test/**', '!/src/**/*.d.ts'],
  { query: '?raw', import: 'default', eager: true },
);

/** Términos técnicos o ejemplos de código que no se traducen, por fichero. */
const ALLOWED: Readonly<Record<string, readonly string[]>> = {
  '/src/components/ResultTable.tsx': ['NULL'],
  '/src/features/explorer/ObjectDetail.tsx': ['DDL', 'PK', 'ON DELETE'],
  '/src/features/runs/ArtifactBrowser.tsx': ['SHA-256'],
  '/src/features/runs/PatternPreview.tsx': ['[ABC]', '[!ABC]', 'MVG_*', 'MVG_*, COB_*', '*_BAK, TMP_*'],
};

/** Atributos JSX cuyo valor ve (u oye) el usuario. */
const TEXT_ATTRS = new Set([
  'aria-label',
  'aria-description',
  'title',
  'placeholder',
  'label',
  'description',
  'alt',
  'legend',
  'error',
  'message',
]);
/** Propiedades de objetos que acaban en pantalla (`ApiError`, notificaciones, opciones de un select). */
const TEXT_PROPS = new Set(['title', 'message', 'label', 'description', 'placeholder']);
const LETTERS = /[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{2,}/;

function flatten(obj: object, prefix = '', out = new Set<string>()): Set<string> {
  for (const [key, value] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value !== null && typeof value === 'object') flatten(value as object, path, out);
    else out.add(path);
  }
  return out;
}

const KEYS = new Set([...flatten(core), ...flatten(features)]);
/** Sufijos de plural y de contexto de i18next (`clave_one`, `clave_migrate_plan`…). */
const ROOTS = new Set(
  [...KEYS].flatMap((key) => key.split('_').map((_, i, parts) => parts.slice(0, i + 1).join('_'))),
);

/** Una clave existe si es una hoja, la raíz de un plural o contexto, o un objeto (`returnObjects`). */
function keyExists(key: string): boolean {
  return KEYS.has(key) || ROOTS.has(key) || [...KEYS].some((k) => k.startsWith(`${key}.`));
}

interface Issue {
  where: string;
  kind: string;
  text: string;
}

/** Literales visibles y claves inexistentes de un fichero. */
function findIssues(file: string, source: string): Issue[] {
  const kind = file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, kind);
  const allowed = new Set(ALLOWED[file] ?? []);
  const issues: Issue[] = [];
  const add = (node: ts.Node, issueKind: string, text: string) => {
    if (allowed.has(text)) return;
    const line = sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1;
    issues.push({ where: `${file}:${line}`, kind: issueKind, text });
  };
  const literal = (node: ts.Node | undefined): string | undefined =>
    node && (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) ? node.text : undefined;

  const visit = (node: ts.Node) => {
    if (ts.isJsxText(node)) {
      const text = node.text.replace(/\s+/g, ' ').trim();
      if (LETTERS.test(text)) add(node, 'texto JSX', text);
    } else if (ts.isJsxAttribute(node) && node.initializer && TEXT_ATTRS.has(node.name.getText(sf))) {
      const init = node.initializer;
      const text = ts.isJsxExpression(init) ? literal(init.expression) : literal(init);
      if (text !== undefined && LETTERS.test(text)) add(node, `atributo ${node.name.getText(sf)}`, text);
    } else if (ts.isPropertyAssignment(node) && TEXT_PROPS.has(node.name.getText(sf))) {
      // Solo frases (con espacio o de una palabra con mayúscula, como «Error»): no claves ni valores técnicos.
      const text = literal(node.initializer);
      if (text !== undefined && LETTERS.test(text) && /\s|^[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+$/.test(text)) {
        add(node, `propiedad ${node.name.getText(sf)}`, text);
      }
    } else if (ts.isCallExpression(node) && /(^|\.)t$/.test(node.expression.getText(sf))) {
      const key = literal(node.arguments[0]);
      if (key !== undefined && !keyExists(key)) add(node, 'clave inexistente', key);
    } else if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.BarBarToken) {
      // Fallbacks de texto: `statusText || 'Error'`.
      const text = literal(node.right);
      if (text !== undefined && /^[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+( [a-záéíóúñ]+)*$/.test(text))
        add(node, 'fallback', text);
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);
  return issues;
}

describe('i18n: textos visibles', () => {
  it('detecta literales, fallbacks y claves inexistentes (autocomprobación)', () => {
    const sample = [
      'const a = <Text title="Hola mundo">Texto fijo</Text>;',
      "const b = <Button aria-label={t('common.cancel')}>{t('no.existe')}</Button>;",
      "const c = { title: 'No se pudo enviar', status: 0 };",
      "const d = response.statusText || 'Error';",
    ].join('\n');
    expect(findIssues('/src/sample.tsx', sample).map((i) => `${i.kind}: ${i.text}`)).toEqual([
      'atributo title: Hola mundo',
      'texto JSX: Texto fijo',
      'clave inexistente: no.existe',
      'propiedad title: No se pudo enviar',
      'fallback: Error',
    ]);
  });

  it('las fuentes no tienen textos visibles fuera de i18n ni claves que no existan', () => {
    expect(Object.keys(SOURCES).length).toBeGreaterThan(50);
    const issues = Object.entries(SOURCES).flatMap(([file, source]) => findIssues(file, source));
    expect(issues.map((i) => `${i.where} [${i.kind}] ${i.text}`)).toEqual([]);
  });
});
