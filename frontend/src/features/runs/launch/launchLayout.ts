import type { Operation, OperationParam } from '../useRuns';

/**
 * Presentación del formulario «Lanzar ejecución»: qué tarjetas tiene cada operación y qué parámetros van en cada una.
 *
 * El backend sigue siendo la fuente de los parámetros (tipo, validación, `group`, `requires`); aquí solo se decide
 * cómo se agrupan en pantalla. Un parámetro que no aparece en ninguna tarjeta se pinta en la tarjeta «Otros»: un
 * campo nuevo del backend nunca desaparece del formulario.
 */

/** Elemento de una tarjeta: un parámetro, una columna de parámetros o un subgrupo con nombre (opciones por motor). */
export type CardItem = string | { stack: readonly string[] } | { group: string };

export interface CardSpec {
  /** Identificador estable (tests, claves de React). */
  id: string;
  /** Clave i18n del título. */
  title: string;
  items: readonly CardItem[];
  /** `full` ocupa todo el ancho de la rejilla. */
  span?: 1 | 'full';
  /** Columnas internas de la tarjeta (en pantallas anchas). */
  cols?: 1 | 2 | 3;
  /** Va en «Opciones avanzadas» (plegado). */
  advanced?: boolean;
  /** Contenido especial de la tarjeta. */
  widget?: 'patternPreview' | 'dumpSelection';
}

/** Tarjeta resuelta contra los parámetros reales de la operación. */
export interface ResolvedCard extends Omit<CardSpec, 'items'> {
  items: ResolvedItem[];
  /** Nombres de todos los parámetros de la tarjeta (para errores y visibilidad). */
  params: string[];
}

export type ResolvedItem =
  | { kind: 'param'; param: OperationParam }
  | { kind: 'stack'; params: OperationParam[] }
  | { kind: 'group'; group: string; params: OperationParam[] };

const SOURCE = (items: readonly string[]): CardSpec => ({ id: 'source', title: 'runs.cards.source', items });
const TARGET = (items: readonly CardItem[]): CardSpec => ({
  id: 'target',
  title: 'runs.cards.target',
  items,
});
const FILTER = (items: readonly string[], widget: NonNullable<CardSpec['widget']>): CardSpec => ({
  id: 'filter',
  title: 'runs.groups.filter',
  items,
  span: 'full',
  widget,
});

export const LAUNCH_LAYOUTS: Readonly<Record<string, readonly CardSpec[]>> = {
  documentation: [
    SOURCE(['connection', 'schema']),
    {
      id: 'formats',
      title: 'runs.groups.formats',
      items: ['word', 'excel', 'html', 'markdown', 'locale'],
      cols: 2,
    },
    {
      id: 'extra',
      title: 'runs.groups.extra',
      items: ['database_info', 'storage', 'engine_conditions', 'charset'],
    },
    {
      id: 'content',
      title: 'runs.cards.content',
      items: [
        { stack: ['tables', 'table_columns', 'table_keys', 'table_indexes', 'table_ddl'] },
        { stack: ['views', 'view_ddl'] },
        { stack: ['routines'] },
      ],
      span: 'full',
      cols: 3,
    },
    FILTER(['table_include', 'table_exclude', 'table_frontier'], 'patternPreview'),
    {
      id: 'graphs',
      title: 'runs.groups.graphs',
      items: [
        'graphs',
        'graph_depth',
        'graph_direction',
        'graph_columns',
        'graph_max_columns',
        'graph_data_types',
        'graph_orthogonal',
      ],
      span: 'full',
      cols: 3,
    },
    { id: 'word', title: 'runs.cards.word', items: ['word_template', 'tables_per_document'] },
    { id: 'excel', title: 'runs.cards.excel', items: ['excel_template'] },
    { id: 'html', title: 'runs.cards.html', items: ['html_items_per_page'] },
    {
      id: 'markdown',
      title: 'runs.groups.markdown',
      items: ['markdown_site_name', 'markdown_diagram_depth', 'trace_map', 'markdown_previous_run'],
      span: 'full',
      cols: 2,
    },
  ],
  relationship_graph: [
    SOURCE(['connection', 'schema', 'table']),
    { id: 'reach', title: 'runs.cards.reach', items: ['max_depth', 'direction', 'max_subnodes'] },
    {
      id: 'appearance',
      title: 'runs.cards.appearance',
      items: ['column_mode', 'max_columns', 'show_data_types', 'orthogonal_edges', 'format'],
    },
  ],
  compare: [
    { ...SOURCE(['source_connection', 'source_schema']), title: 'runs.cards.compareSource' },
    { ...TARGET(['target_connection', 'target_schema']), title: 'runs.cards.compareTarget' },
    {
      id: 'scope',
      title: 'runs.groups.scope',
      items: [{ stack: ['tables', 'indexes', 'foreign_keys', 'comments'] }, { stack: ['views', 'routines'] }],
      cols: 2,
    },
    {
      id: 'reports',
      title: 'runs.groups.reports',
      items: [{ stack: ['html', 'excel', 'word', 'markdown'] }, { stack: ['sql', 'sql_dialect', 'locale'] }],
      cols: 2,
    },
  ],
  migrate_plan: [
    SOURCE(['source_connection', 'source_schema']),
    TARGET([
      'target_engine',
      { group: 'mysql' },
      { group: 'sqlserver' },
      { group: 'postgresql' },
      { group: 'oracle' },
    ]),
    { id: 'general', title: 'runs.groups.general', items: ['view_strategy', 'number_fallback'] },
    FILTER(['table_include', 'table_exclude'], 'patternPreview'),
  ],
  dump_preview: [
    SOURCE(['source_connection', 'source_schema']),
    TARGET(['target_connection', 'target_schema']),
    FILTER(['tables', 'table_include', 'table_exclude'], 'dumpSelection'),
    {
      id: 'loadErrors',
      title: 'runs.cards.loadErrors',
      items: ['truncate_target', 'sync_pk_sequences', 'on_error', 'max_rejects', 'locale'],
      cols: 2,
      span: 'full',
    },
    {
      id: 'performance',
      title: 'runs.groups.performance',
      items: ['chunk_size', 'max_parallel_tables', 'manage_indexes'],
      advanced: true,
      span: 'full',
      cols: 3,
    },
  ],
};

/**
 * Parámetros que se muestran desactivados mientras su interruptor principal esté apagado (util_bbdd los ignora sin
 * él); a diferencia de `requires`, se siguen enviando.
 */
export const DISABLED_WITHOUT: Readonly<Record<string, Readonly<Record<string, string>>>> = {
  documentation: {
    table_columns: 'tables',
    table_keys: 'tables',
    table_indexes: 'tables',
    table_ddl: 'tables',
    view_ddl: 'views',
    graph_depth: 'graphs',
    graph_direction: 'graphs',
    graph_columns: 'graphs',
    graph_max_columns: 'graphs',
    graph_data_types: 'graphs',
    graph_orthogonal: 'graphs',
  },
};

/** Visibilidad que depende del valor (no booleano) de otro campo: se oculta, vuelve a su valor por defecto y no se envía. */
export const SHOWN_WHEN: Readonly<
  Record<string, Readonly<Record<string, { param: string; value: string }>>>
> = {
  dump_preview: { max_rejects: { param: 'on_error', value: 'isolate' } },
};

/** Grupos de `migrate_plan` que solo aplican a un motor destino: se ocultan para los demás. */
export const ENGINE_GROUPS: Readonly<Record<string, readonly string[]>> = {
  mysql: ['mariadb', 'mysql'],
  sqlserver: ['sqlserver'],
  postgresql: ['postgresql'],
  oracle: ['oracle'],
};

/** Grupos de la lista de operaciones, en orden; la primera operación disponible es la elegida al abrir. */
export const OPERATION_CATEGORIES: readonly { key: string; operations: readonly string[] }[] = [
  { key: 'document', operations: ['documentation', 'relationship_graph'] },
  { key: 'compare', operations: ['compare'] },
  { key: 'move', operations: ['migrate_plan', 'dump_preview'] },
  { key: 'diagnostics', operations: ['noop'] },
];

/** Operaciones agrupadas por categoría; las que no están en ninguna van en «Otras», antes de «Diagnóstico». */
export function categorize(operations: readonly Operation[]): { key: string; operations: Operation[] }[] {
  const known = new Set(OPERATION_CATEGORIES.flatMap((c) => c.operations));
  const pick = (names: readonly string[]) =>
    names.flatMap((name) => operations.filter((op) => op.name === name));
  const categories = OPERATION_CATEGORIES.map((c) => ({ key: c.key, operations: pick(c.operations) }));
  const others = operations.filter((op) => !known.has(op.name));
  if (others.length > 0) categories.splice(categories.length - 1, 0, { key: 'other', operations: others });
  return categories.filter((c) => c.operations.length > 0);
}

/** Tarjetas por defecto: los parámetros sin grupo en «Parámetros» y una tarjeta por grupo, en orden de aparición. */
function defaultLayout(params: readonly OperationParam[]): CardSpec[] {
  const groups = new Map<string | null, string[]>();
  for (const param of params) {
    const key = param.group ?? null;
    groups.set(key, [...(groups.get(key) ?? []), param.name]);
  }
  return [...groups.entries()].map(([group, items]) =>
    group === null
      ? { id: 'main', title: 'runs.cards.params', items, cols: 2 }
      : { id: `group-${group}`, title: `runs.groups.${group}`, items, cols: 2 },
  );
}

/**
 * Tarjetas de `operation` con sus parámetros reales. Los nombres del diseño que la operación no tiene se ignoran y
 * los parámetros que el diseño no coloca van a la tarjeta «Otros», al final.
 */
export function resolveCards(operation: Operation): ResolvedCard[] {
  const byName = new Map(operation.params.map((p) => [p.name, p]));
  const placed = new Set<string>();
  const take = (name: string): OperationParam[] => {
    const param = byName.get(name);
    if (!param || placed.has(name)) return [];
    placed.add(name);
    return [param];
  };
  const specs = LAUNCH_LAYOUTS[operation.name] ?? defaultLayout(operation.params);
  const cards: ResolvedCard[] = specs.map(({ items, ...spec }) => {
    const resolved: ResolvedItem[] = items.flatMap((item): ResolvedItem[] => {
      if (typeof item === 'string') return take(item).map((param) => ({ kind: 'param', param }));
      if ('stack' in item) {
        const params = item.stack.flatMap(take);
        return params.length > 0 ? [{ kind: 'stack', params }] : [];
      }
      const params = operation.params.filter((p) => p.group === item.group).flatMap((p) => take(p.name));
      return params.length > 0 ? [{ kind: 'group', group: item.group, params }] : [];
    });
    return { ...spec, items: resolved, params: resolved.flatMap(itemParams).map((p) => p.name) };
  });
  const rest = operation.params.filter((p) => !placed.has(p.name));
  if (rest.length > 0) {
    cards.push({
      id: 'other',
      title: 'runs.cards.other',
      cols: 2,
      span: 'full',
      items: rest.map((param) => ({ kind: 'param', param })),
      params: rest.map((p) => p.name),
    });
  }
  return cards.filter((card) => card.items.length > 0);
}

export function itemParams(item: ResolvedItem): OperationParam[] {
  return item.kind === 'param' ? [item.param] : item.params;
}
