import { useQuery } from '@tanstack/react-query';

import { api, unwrap } from '../../../api/client';
import type { components } from '../../../api/schema';

export type DumpPreview = components['schemas']['DumpPreviewOut'];
export type DumpPreviewTable = components['schemas']['DumpPreviewTableOut'];
export type DumpResult = components['schemas']['DumpResultOut'];

/** Antigüedad máxima de la vista previa que permite volcar (la API lo vuelve a comprobar). */
export const PREVIEW_MAX_AGE_MS = 60 * 60 * 1000;
export const TRUNCATE_WORD = 'VACIAR';

export function useDumpPreview(runId: string) {
  return useQuery({
    queryKey: ['runs', runId, 'dump-preview'],
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/runs/{run_id}/dump-preview', { params: { path: { run_id: runId } } })),
    staleTime: Infinity,
  });
}

export function useDumpResult(runId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['runs', runId, 'dump-result'],
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/runs/{run_id}/dump-result', { params: { path: { run_id: runId } } })),
    enabled,
    staleTime: Infinity,
    retry: false,
  });
}

/** Constraints que un volcado interrumpido dejó desactivadas (G31); se repite mientras haya una restauración en marcha. */
export function useDumpConstraints(runId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['runs', runId, 'dump-constraints'],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/runs/{run_id}/dump-constraints', { params: { path: { run_id: runId } } }),
      ),
    enabled,
    refetchInterval: (query) => (query.state.data?.restore_run ? 3000 : false),
  });
}

/** Volcados lanzados desde una vista previa (más recientes primero). */
export function usePreviewDumps(projectId: number, previewId: string) {
  return useQuery({
    queryKey: ['projects', projectId, 'runs', 'dump-apply', previewId],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/runs', {
          params: {
            path: { project_id: projectId },
            query: { operation: 'dump_apply', limit: 50, offset: 0 },
          },
        }),
      ),
    select: (page) => page.items.filter((run) => run.params['preview_run'] === previewId),
    refetchInterval: (query) =>
      query.state.data?.items.some((run) => run.status === 'queued' || run.status === 'running')
        ? 3000
        : false,
  });
}

/** Filas que se borrarán al vaciar el destino (las de las tablas que existen en él). */
export function rowsToDelete(preview: DumpPreview): number {
  return preview.tables.reduce((sum, table) => sum + (table.target_rows ?? 0), 0);
}
