import type { Project } from '../features/projects/useProjects';
import type { Operation, Run, RunDetail } from '../features/runs/useRuns';

export const PROJECT: Project = {
  id: 5,
  name: 'Migración 2026',
  description: 'Pruebas',
  owner_id: 1,
  my_role: 'owner',
  created_at: '2026-10-20T08:00:00Z',
  updated_at: '2026-10-20T08:00:00Z',
};

export const RUN_ID = '01JABCDEFGHJKMNPQRSTVWXYZ0';

export const RUN: Run = {
  id: RUN_ID,
  project_id: 5,
  project_name: 'Migración 2026',
  operation: 'noop',
  params: { steps: 2, step_seconds: 1, fail: false, connection: null },
  status: 'running',
  phase: 'running',
  progress_message: 'Paso 1 de 2',
  progress_pct: 50,
  error_code: null,
  error_message: null,
  cancel_requested: false,
  user_id: 1,
  username: 'admin',
  created_at: '2026-10-20T08:00:00Z',
  started_at: '2026-10-20T08:00:01Z',
  finished_at: null,
  duration_seconds: null,
  size_bytes: 0,
  artifacts_count: 0,
  relaunched_from: null,
};

export const RUN_DETAIL: RunDetail = { ...RUN, my_role: 'owner', artifacts: [] };

export const FINISHED: RunDetail = {
  ...RUN_DETAIL,
  status: 'succeeded',
  phase: 'done',
  progress_message: null,
  progress_pct: 100,
  finished_at: '2026-10-20T08:00:04Z',
  duration_seconds: 3,
  size_bytes: 2048,
  artifacts_count: 2,
  artifacts: [
    {
      id: 11,
      path: 'outputs/html/resumen.html',
      kind: 'html',
      mime: 'text/html',
      size_bytes: 1024,
      sha256: 'a'.repeat(64),
      created_at: '2026-10-20T08:00:04Z',
      previewable: true,
    },
    {
      id: 12,
      path: 'outputs/sql/ejemplo.sql',
      kind: 'sql',
      mime: 'application/sql',
      size_bytes: 1024,
      sha256: 'b'.repeat(64),
      created_at: '2026-10-20T08:00:04Z',
      previewable: true,
    },
  ],
};

export const NOOP: Operation = {
  name: 'noop',
  title: 'Prueba del motor de ejecuciones',
  description: 'Simula una ejecución',
  params: [
    {
      name: 'steps',
      type: 'integer',
      required: false,
      default: 3,
      description: 'Pasos',
      minimum: 1,
      maximum: 20,
    },
    {
      name: 'step_seconds',
      type: 'float',
      required: false,
      default: 1,
      description: 'Espera',
      minimum: 0,
      maximum: 30,
    },
    {
      name: 'fail',
      type: 'boolean',
      required: false,
      default: false,
      description: 'Fallo',
      minimum: null,
      maximum: null,
    },
    {
      name: 'connection',
      type: 'connection',
      required: false,
      default: null,
      description: 'Conexión',
      minimum: null,
      maximum: null,
    },
  ],
};

const param = (
  name: string,
  type: Operation['params'][number]['type'],
  extra: Partial<Operation['params'][number]> = {},
): Operation['params'][number] => ({
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

export const DOCUMENTATION: Operation = {
  name: 'documentation',
  title: 'Documentación de la base de datos',
  description: 'Documenta un schema',
  params: [
    param('connection', 'connection', { required: true }),
    param('schema', 'string'),
    param('word', 'boolean', { default: true, group: 'formats' }),
    param('html', 'boolean', { default: true, group: 'formats' }),
    param('graph_direction', 'string', {
      default: 'both',
      group: 'graphs',
      options: ['both', 'outgoing', 'incoming'],
    }),
  ],
};

export const ORACLE_CONNECTION = {
  id: 3,
  alias: 'ventas',
  connection_id: 9,
  connection_name: 'Ventas Oracle',
  db_type: 'oracle',
  read_only: true,
  created_at: '2026-10-20T08:00:00Z',
};

const artifact = (id: number, path: string, kind: string, previewable = false) => ({
  id,
  path,
  kind,
  mime: 'application/octet-stream',
  size_bytes: 2048,
  sha256: 'c'.repeat(64),
  created_at: '2026-10-20T08:00:04Z',
  previewable,
});

export const SITE_URL = `/api/v1/runs/${RUN_ID}/site/1.1900000000.abc/documentacion/index.html`;

export const DOC_RUN: RunDetail = {
  ...FINISHED,
  operation: 'documentation',
  params: { connection: 'origen', schema: null, word: true, html: true, graph_direction: 'both' },
  site_url: SITE_URL,
  artifacts: [
    artifact(21, 'outputs/word/documentacion.docx', 'word'),
    artifact(22, 'outputs/excel/documentacion.xlsx', 'excel'),
    artifact(23, 'outputs/html/documentacion/index.html', 'html', true),
    artifact(24, 'outputs/html/documentacion/assets/sql-highlight.js', 'html'),
    artifact(25, 'outputs/markdown/resumen.md', 'markdown', true),
  ],
};

export const GRAPH_RUN: RunDetail = {
  ...FINISHED,
  operation: 'relationship_graph',
  params: { connection: 'origen', table: 'pedidos' },
  artifacts: [
    artifact(31, 'outputs/graphs/pedidos.svg', 'graphs', true),
    artifact(32, 'outputs/graphs/pedidos_2.svg', 'graphs', true),
  ],
};

export const OLD_COMPARE_ID = '01JOLDCOMPARE0000000000000';

export const COMPARE_RUN: RunDetail = {
  ...FINISHED,
  operation: 'compare',
  params: { source_connection: 'origen', target_connection: 'destino' },
  site_url: `/api/v1/runs/${RUN_ID}/site/1.1900000000.abc/comparacion/index.html`,
  artifacts: [
    artifact(41, 'outputs/diff/schema_diff.json', 'diff'),
    artifact(42, 'outputs/html/comparacion/index.html', 'html', true),
    artifact(43, 'outputs/sql/comparacion.sql', 'sql', true),
    artifact(44, 'outputs/excel/comparacion.xlsx', 'excel'),
  ],
};

export const SCHEMA_DIFF = {
  source_label: 'origen (sqlite)',
  target_label: 'destino (sqlite)',
  summary: 'Tablas: 1 añadidas, 1 eliminadas, 1 modificadas | Vistas: 1 diferencias',
  has_differences: true,
  total_differences: 4,
  total_leaf_differences: 5,
  table_diffs: [
    { table_name: 'facturas', status: 'added' },
    { table_name: 'auditoria', status: 'removed' },
    {
      table_name: 'clientes',
      status: 'modified',
      column_diffs: [
        { column_name: 'nombre', attribute: 'nullable', source_value: 'False', target_value: 'True' },
      ],
      index_diffs: [
        {
          index_name: 'ix_clientes_nombre',
          table_name: 'clientes',
          status: 'added',
          source_columns: 'nombre',
          target_columns: '',
          source_unique: false,
          target_unique: false,
        },
      ],
      fk_diffs: [],
      comment_diffs: [],
    },
  ],
  view_diffs: [
    {
      view_name: 'v_clientes',
      status: 'modified',
      source_definition: 'SELECT id,\n  nombre\nFROM clientes',
      target_definition: 'SELECT id\nFROM clientes',
    },
  ],
  routine_diffs: [],
};

export const EVOLUTION = {
  run_id: RUN_ID,
  baseline_id: OLD_COMPARE_ID,
  labels_match: false,
  new: [
    {
      kind: 'column',
      table: 'clientes',
      name: 'nombre',
      attribute: 'nullable',
      status: 'modified',
      source: 'False',
      target: 'True',
    },
  ],
  resolved: [
    { kind: 'table', table: null, name: 'pedidos', attribute: null, status: 'added', source: '', target: '' },
  ],
  persisting: [],
};
