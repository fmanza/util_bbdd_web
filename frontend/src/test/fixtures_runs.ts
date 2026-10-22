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
