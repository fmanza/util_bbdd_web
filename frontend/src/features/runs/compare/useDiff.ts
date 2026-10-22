import { useQuery } from '@tanstack/react-query';

import { api, unwrap } from '../../../api/client';
import type { components } from '../../../api/schema';

export type SchemaDiff = components['schemas']['SchemaDiffOut'];
export type TableDiff = components['schemas']['TableDiffOut'];
export type DiffStatus = TableDiff['status'];
export type DiffItem = components['schemas']['DiffItemOut'];
export type DiffEvolution = components['schemas']['DiffEvolutionOut'];

/** Diff de una ejecución `compare` correcta (no cambia: no se refresca). */
export function useRunDiff(runId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['runs', runId, 'diff'],
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/runs/{run_id}/diff', { params: { path: { run_id: runId } } })),
    enabled,
    staleTime: Infinity,
  });
}

/** Comparaciones correctas del proyecto que pueden servir de referencia (sin la actual). */
export function useBaselineCandidates(projectId: number, runId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['projects', projectId, 'runs', 'compare-baselines'],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/runs', {
          params: {
            path: { project_id: projectId },
            query: { operation: 'compare', status: 'succeeded', limit: 50, offset: 0 },
          },
        }),
      ),
    select: (page) => page.items.filter((run) => run.id !== runId),
    enabled,
  });
}

export function useDiffEvolution(runId: string, baseline: string | null) {
  return useQuery({
    queryKey: ['runs', runId, 'diff', 'evolution', baseline],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/runs/{run_id}/diff/evolution', {
          params: { path: { run_id: runId }, query: { baseline: baseline ?? '' } },
        }),
      ),
    enabled: baseline !== null,
    staleTime: Infinity,
  });
}
