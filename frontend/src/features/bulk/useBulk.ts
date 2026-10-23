import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, ensureOk, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type Upload = components['schemas']['UploadOut'];
export type UploadInfo = components['schemas']['UploadInfoOut'];
export type BulkPreview = components['schemas']['BulkPreviewOut'];
export type BulkResult = components['schemas']['BulkResultOut'];

export interface ReadOptions {
  sheet: string | null;
  delimiter: string | null;
  encoding: string | null;
}

const uploadsKey = (projectId: number) => ['projects', projectId, 'uploads'] as const;

export function useUploads(projectId: number) {
  return useQuery({
    queryKey: uploadsKey(projectId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/uploads', {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
}

/** Sube un fichero (`multipart/form-data`; el cliente añade la cabecera CSRF). */
export function useUploadFile(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) =>
      unwrap(
        await api.POST('/api/v1/projects/{project_id}/uploads', {
          params: { path: { project_id: projectId } },
          body: { file: file as unknown as string },
          bodySerializer: (body) => {
            const form = new FormData();
            form.append('file', body.file as unknown as Blob);
            return form;
          },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: uploadsKey(projectId) }),
  });
}

export function useDeleteUpload(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (uploadId: string) =>
      ensureOk(
        await api.DELETE('/api/v1/projects/{project_id}/uploads/{upload_id}', {
          params: { path: { project_id: projectId, upload_id: uploadId } },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: uploadsKey(projectId) }),
  });
}

/** Columnas, primeras filas y hojas o separador detectado, con las opciones de lectura elegidas. */
export function useUploadInfo(projectId: number, uploadId: string | null, options: ReadOptions) {
  return useQuery({
    queryKey: [...uploadsKey(projectId), uploadId, 'info', options],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/uploads/{upload_id}/info', {
          params: {
            path: { project_id: projectId, upload_id: uploadId ?? '' },
            query: {
              sheet: options.sheet,
              delimiter: options.delimiter,
              encoding: options.encoding,
            },
          },
        }),
      ),
    enabled: uploadId !== null,
    retry: false,
  });
}

export function useBulkPreview(runId: string) {
  return useQuery({
    queryKey: ['runs', runId, 'bulk-preview'],
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/runs/{run_id}/bulk-preview', { params: { path: { run_id: runId } } })),
    staleTime: Infinity,
  });
}

export function useBulkResult(runId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['runs', runId, 'bulk-result'],
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/runs/{run_id}/bulk-result', { params: { path: { run_id: runId } } })),
    enabled,
    staleTime: Infinity,
    retry: false,
  });
}

/** Columna de la tabla para una columna del fichero: misma, sin distinguir mayúsculas (o ninguna). */
export function suggestTarget(column: string, tableColumns: string[]): string {
  return tableColumns.find((name) => name.toLowerCase() === column.toLowerCase()) ?? '';
}
