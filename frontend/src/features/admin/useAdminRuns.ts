import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, ensureOk, unwrap } from '../../api/client';
import type { components, operations } from '../../api/schema';
import { PAGE_SIZE, type SortState } from '../../components/tableState';

export type AdminRun = components['schemas']['AdminRunOut'];
export type AdminRunSort = NonNullable<
  operations['list_runs_api_v1_admin_runs_get']['parameters']['query']
>['sort'];
export type ProjectRunsDeleteResult = components['schemas']['ProjectRunsDeleteOut'];
type RunStatus = AdminRun['status'];

export interface AdminRunFilters {
  q: string;
  status: RunStatus | null;
  page: number;
  sort: SortState | null;
}

/** Ejecuciones de todos los proyectos (solo metadatos), 25 por página. */
export function useAdminRuns({ q, status, page, sort }: AdminRunFilters) {
  return useQuery({
    queryKey: ['admin', 'runs', { q, status, page, sort }],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/admin/runs', {
          params: {
            query: {
              q: q || null,
              status,
              sort: (sort?.key ?? null) as NonNullable<AdminRunSort> | null,
              order: sort?.order ?? null,
              limit: PAGE_SIZE,
              offset: (page - 1) * PAGE_SIZE,
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useProjectRunsSummary(projectId: number | null) {
  return useQuery({
    queryKey: ['admin', 'projects', projectId, 'runs-summary'],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/admin/projects/{project_id}/runs/summary', {
          params: { path: { project_id: projectId ?? 0 } },
        }),
      ),
    enabled: projectId !== null,
  });
}

function useInvalidateRuns() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ['admin'] }),
      queryClient.invalidateQueries({ queryKey: ['runs'] }),
      queryClient.invalidateQueries({ queryKey: ['projects'] }),
    ]);
}

export function useDeleteRun() {
  const invalidate = useInvalidateRuns();
  return useMutation({
    mutationFn: async (runId: string) =>
      ensureOk(await api.DELETE('/api/v1/admin/runs/{run_id}', { params: { path: { run_id: runId } } })),
    onSuccess: invalidate,
  });
}

export function useDeleteProjectRuns() {
  const invalidate = useInvalidateRuns();
  return useMutation({
    mutationFn: async ({ projectId, confirm }: { projectId: number; confirm: string }) =>
      unwrap(
        await api.POST('/api/v1/admin/projects/{project_id}/runs/delete', {
          params: { path: { project_id: projectId } },
          body: { confirm },
        }),
      ),
    onSuccess: invalidate,
  });
}
