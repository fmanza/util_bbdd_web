import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { ApiError, type Problem, api, ensureOk, unwrap } from '../../api/client';
import type { components, paths } from '../../api/schema';
import { type ListState, listQuery } from '../../components/useListState';

export type Run = components['schemas']['RunOut'];
export type RunDetail = components['schemas']['RunDetailOut'];
export type RunStatus = Run['status'];
export type Artifact = components['schemas']['ArtifactOut'];
export type Operation = components['schemas']['OperationOut'];
export type OperationParam = components['schemas']['OperationParamOut'];
export type MarkdownPages = components['schemas']['MarkdownPagesOut'];

/** Ejecuciones anteriores que se ofrecen en el formulario (no es una lista paginada). */
const PICKER_SIZE = 50;
type RunSort = NonNullable<NonNullable<paths['/api/v1/runs']['get']['parameters']['query']>['sort']>;
export const ACTIVE_STATUSES: readonly RunStatus[] = ['queued', 'running'];

export function isActive(status: RunStatus | undefined): boolean {
  return status !== undefined && ACTIVE_STATUSES.includes(status);
}

export function useProjectRuns(projectId: number, status: RunStatus | null, list: ListState) {
  return useQuery({
    queryKey: ['projects', projectId, 'runs', { status, ...list }],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/runs', {
          params: {
            path: { project_id: projectId },
            query: { status, ...listQuery<RunSort>(list) },
          },
        }),
      ),
    placeholderData: keepPreviousData,
    // Mientras haya ejecuciones activas, el historial se refresca solo (el detalle usa SSE).
    refetchInterval: (query) => (query.state.data?.items.some((run) => isActive(run.status)) ? 3000 : false),
  });
}

/** Ejecuciones correctas de `operation` en el proyecto (las 50 últimas), para elegir una anterior en el formulario. */
export function useSucceededRuns(projectId: number, operation: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ['projects', projectId, 'runs', { operation, status: 'succeeded' }],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/runs', {
          params: {
            path: { project_id: projectId },
            query: { status: 'succeeded', operation, limit: PICKER_SIZE, offset: 0 },
          },
        }),
      ),
    enabled: enabled && operation !== null,
  });
}

export function useMyRuns(list: ListState) {
  return useQuery({
    queryKey: ['runs', 'mine', list],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/runs', {
          params: { query: listQuery<RunSort>(list) },
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
    const reload = () => {
      void queryClient.invalidateQueries({ queryKey: runKey(id) });
      void queryClient.invalidateQueries({ queryKey: ['projects'] });
    };
    source.addEventListener('run', (event: MessageEvent<string>) => {
      const snapshot = JSON.parse(event.data) as Run;
      queryClient.setQueryData<RunDetail>(runKey(id), (previous) =>
        previous ? { ...previous, ...snapshot } : previous,
      );
      // Al pasar a terminal, el efecto se desmonta y cierra la fuente antes de que llegue `end`: se recarga ya el
      // detalle (artefactos) en lugar de depender de ese evento.
      if (!isActive(snapshot.status)) {
        source.close();
        reload();
      }
    });
    source.addEventListener('end', () => {
      source.close();
      reload();
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
        // El *problem details* de la API (p. ej. 413 «demasiado grande, descárgalo») en lugar de un error genérico.
        const problem = (await response.json().catch(() => null)) as Problem | null;
        throw new ApiError(
          problem?.title ? problem : { title: response.statusText || 'Error', status: response.status },
        );
      }
      return response.text();
    },
    enabled: artifact !== null,
    staleTime: Infinity,
  });
}

/** Índice de páginas de la documentación Markdown (util_bbdd 5.4.0, G51); la ejecución está cerrada: no caduca. */
export function useMarkdownPages(runId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['runs', runId, 'markdown-pages'],
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/runs/{run_id}/markdown-pages', { params: { path: { run_id: runId } } })),
    enabled,
    staleTime: Infinity,
  });
}

export const previewUrl = (runId: string, artifactId: number) =>
  `/api/v1/runs/${encodeURIComponent(runId)}/artifacts/${artifactId}/preview`;
export const downloadUrl = (runId: string, artifactId: number) =>
  `/api/v1/runs/${encodeURIComponent(runId)}/artifacts/${artifactId}`;
/** Formatos de la documentación con ZIP propio (`?format=`). */
export type DocumentationFormat = 'word' | 'excel' | 'html' | 'markdown';
export const archiveUrl = (runId: string, format?: DocumentationFormat) =>
  `/api/v1/runs/${encodeURIComponent(runId)}/archive${format ? `?format=${format}` : ''}`;

/** Ficheros del sitio HTML (subcarpetas de `outputs/html/`): se ven en el iframe de la documentación, no en la lista. */
export function isSiteFile(artifact: Artifact): boolean {
  return artifact.kind === 'html' && artifact.path.split('/').length > 3;
}

/** Carpeta de la documentación Markdown (util_bbdd 5.3.0): miles de ficheros que se ven en su tarjeta, no en la lista. */
export const MARKDOWN_DOC_ROOT = 'outputs/markdown/documentacion/';

export function isMarkdownDocFile(artifact: Artifact): boolean {
  return artifact.kind === 'markdown' && artifact.path.startsWith(MARKDOWN_DOC_ROOT);
}
