import { useQuery } from '@tanstack/react-query';

import { api, unwrap } from '../../../api/client';
import type { components } from '../../../api/schema';
import type { RunDetail } from '../useRuns';

export type MigrationPlan = components['schemas']['MigrationPlanOut'];
export type MigrationReport = components['schemas']['MigrationReportOut'];
export type PlanWarning = components['schemas']['PlanWarningOut'];
export type FkMismatch = components['schemas']['FkMismatchOut'];

/** Antigüedad máxima del modo seco que permite aplicar (la API lo vuelve a comprobar). */
export const DRY_RUN_MAX_AGE_MS = 60 * 60 * 1000;

export function usePlan(runId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['runs', runId, 'plan'],
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/runs/{run_id}/plan', { params: { path: { run_id: runId } } })),
    enabled,
    staleTime: Infinity,
  });
}

export function useMigrationReport(runId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['runs', runId, 'migration-report'],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/runs/{run_id}/migration-report', { params: { path: { run_id: runId } } }),
      ),
    enabled,
    staleTime: Infinity,
    retry: false,
  });
}

/** Ejecuciones `migrate_apply` del proyecto para un plan (modos secos y aplicaciones), más recientes primero. */
export function usePlanApplications(projectId: number, planId: string) {
  return useQuery({
    queryKey: ['projects', projectId, 'runs', 'migrate-apply', planId],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/runs', {
          params: {
            path: { project_id: projectId },
            query: { operation: 'migrate_apply', limit: 50, offset: 0 },
          },
        }),
      ),
    select: (page) => page.items.filter((run) => run.params['plan_run'] === planId),
    refetchInterval: (query) =>
      query.state.data?.items.some((run) => run.status === 'queued' || run.status === 'running')
        ? 3000
        : false,
  });
}

/** Un modo seco correcto, del destino elegido y de hace menos de una hora, permite aplicar. */
export function usableDryRun(
  run: Pick<RunDetail, 'params' | 'status' | 'finished_at'>,
  target: string,
  now: number,
) {
  return (
    run.status === 'succeeded' &&
    run.params['mode'] === 'dry_run' &&
    run.params['target_connection'] === target &&
    run.finished_at !== null &&
    now - new Date(run.finished_at).getTime() < DRY_RUN_MAX_AGE_MS
  );
}
