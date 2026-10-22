import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { api, ensureOk, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type Run = components['schemas']['RunOut'];
export type RunDetail = components['schemas']['RunDetailOut'];
export type RunStatus = Run['status'];
export type Artifact = components['schemas']['ArtifactOut'];
export type Operation = components['schemas']['OperationOut'];
export type OperationParam = components['schemas']['OperationParamOut'];

export const PAGE_SIZE = 50;
export const ACTIVE_STATUSES: readonly RunStatus[] = ['queued', 'running'];

export function isActive(status: RunStatus | undefined): boolean {
  return status !== undefined && ACTIVE_STATUSES.includes(status);
}

export interface RunFilters {
  status: RunStatus | null;
  q: string;
}

export function useProjectRuns(projectId: number, filters: RunFilters, page: number) {
  return useQuery({
    queryKey: ['projects', projectId, 'runs', { ...filters, page }],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/runs', {
          params: {
            path: { project_id: projectId },
            query: {
              status: filters.status,
              q: filters.q || null,
              limit: PAGE_SIZE,
              offset: (page - 1) * PAGE_SIZE,
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
    // Mientras haya ejecuciones activas, el historial se refresca solo (el detalle usa SSE).
    refetchInterval: (query) => (query.state.data?.items.some((run) => isActive(run.status)) ? 3000 : false),
  });
}

export function useMyRuns(page: number) {
  return useQuery({
    queryKey: ['runs', 'mine', { page }],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/runs', {
          params: { query: { limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE } },
        }),
      ),
    placeholderData: keepPreviousData,
    refetchInterval: (query) => (query.state.data?.items.some((run) => isActive(run.status)) ? 5000 : false),
  });
}

export function useOperations() {
  return useQuery({
    queryKey: ['operations'],
    queryFn: async () => unwrap(await api.GET('/api/v1/operations')),
    staleTime: 60 * 60_000,
  });
}

export function useLaunchRun(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: components['schemas']['RunCreate']) =>
      unwrap(
        await api.POST('/api/v1/projects/{project_id}/runs', {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'runs'] }),
        queryClient.invalidateQueries({ queryKey: ['runs', 'mine'] }),
      ]),
  });
}

export const runKey = (id: string) => ['runs', id] as const;

/**
 * Detalle de una ejecución con progreso en vivo por SSE (`/runs/{id}/events`).
 *
 * Mientras esté en cola o en curso, cada evento `run` actualiza la caché del detalle y `end` lo recarga (artefactos).
 * Si `EventSource` no existe o falla, se pasa a sondeo cada 2 s (`polling = true`).
 */
export function useLiveRun(id: string) {
  const queryClient = useQueryClient();
  const [sseFailed, setSseFailed] = useState(false);
  const polling = sseFailed || typeof EventSource === 'undefined';
  const query = useQuery({
    queryKey: runKey(id),
    queryFn: async () => unwrap(await api.GET('/api/v1/runs/{run_id}', { params: { path: { run_id: id } } })),
    refetchInterval: (q) => (polling && isActive(q.state.data?.status) ? 2000 : false),
  });
  const active = isActive(query.data?.status);
  useEffect(() => {
    if (!active || typeof EventSource === 'undefined') {
      return undefined;
    }
    const source = new EventSource(`/api/v1/runs/${encodeURIComponent(id)}/events`, {
      withCredentials: true,
    });
    source.addEventListener('run', (event: MessageEvent<string>) => {
      const snapshot = JSON.parse(event.data) as Run;
      queryClient.setQueryData<RunDetail>(runKey(id), (previous) =>
        previous ? { ...previous, ...snapshot } : previous,
      );
    });
    source.addEventListener('end', () => {
      source.close();
      void queryClient.invalidateQueries({ queryKey: runKey(id) });
      void queryClient.invalidateQueries({ queryKey: ['projects'] });
    });
    source.onerror = () => {
      source.close();
      setSseFailed(true);
    };
    return () => source.close();
  }, [id, active, queryClient]);
  return { ...query, polling };
}

export function useCancelRun(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.POST('/api/v1/runs/{run_id}/cancel', { params: { path: { run_id: id } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: runKey(id) }),
  });
}

export function useRelaunchRun(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.POST('/api/v1/runs/{run_id}/relaunch', { params: { path: { run_id: id } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects'] }),
  });
}

export function usePurgeRun(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      ensureOk(await api.DELETE('/api/v1/runs/{run_id}', { params: { path: { run_id: id } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: runKey(id) }),
  });
}

/** Texto de un artefacto de texto (Markdown, SQL, log, run.json) para la vista previa. */
export function useArtifactText(runId: string, artifact: Artifact | null) {
  return useQuery({
    queryKey: ['runs', runId, 'artifacts', artifact?.id, 'text'],
    queryFn: async () => {
      const url = new URL(previewUrl(runId, artifact?.id ?? 0), globalThis.location.origin);
      const response = await globalThis.fetch(new Request(url, { credentials: 'same-origin' }));
      if (!response.ok) {
        throw new Error(response.statusText || String(response.status));
      }
      return response.text();
    },
    enabled: artifact !== null,
    staleTime: Infinity,
  });
}

export const previewUrl = (runId: string, artifactId: number) =>
  `/api/v1/runs/${encodeURIComponent(runId)}/artifacts/${artifactId}/preview`;
export const downloadUrl = (runId: string, artifactId: number) =>
  `/api/v1/runs/${encodeURIComponent(runId)}/artifacts/${artifactId}`;
export const archiveUrl = (runId: string) => `/api/v1/runs/${encodeURIComponent(runId)}/archive`;
