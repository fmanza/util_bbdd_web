import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';

import {
  ApiError,
  api,
  CSRF_COOKIES,
  CSRF_HEADER,
  ensureOk,
  type Problem,
  readCookie,
  unwrap,
} from '../../api/client';
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

/** Bytes enviados de una subida en curso. */
export interface UploadProgress {
  loaded: number;
  total: number;
}

/** Si el error es la cancelación de una subida (no se muestra como error). */
export function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}

/**
 * `POST …/uploads` como `multipart/form-data` con `XMLHttpRequest`: `fetch` no informa del avance de lo que se envía,
 * y un fichero de cientos de MB necesita barra de progreso. Misma cabecera CSRF y mismos errores (`ApiError` con el
 * *problem details*) que el cliente generado.
 */
function sendUpload(
  projectId: number,
  file: File,
  onProgress: (progress: UploadProgress) => void,
  signal: AbortSignal,
): Promise<Upload> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `/api/v1/projects/${projectId}/uploads`);
    xhr.withCredentials = true;
    const token = CSRF_COOKIES.map(readCookie).find(Boolean);
    if (token) xhr.setRequestHeader(CSRF_HEADER, token);
    xhr.upload.onprogress = (event) =>
      onProgress({ loaded: event.loaded, total: event.lengthComputable ? event.total : file.size });
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        // un proxy puede responder HTML (p. ej. 413 de nginx): queda el estado
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as Upload);
        return;
      }
      const problem = (body as Problem | null) ?? { title: xhr.statusText || 'Error', status: xhr.status };
      const requestId = problem.request_id ?? xhr.getResponseHeader('X-Request-ID') ?? undefined;
      reject(
        new ApiError(requestId ? { ...problem, request_id: requestId } : { ...problem, status: xhr.status }),
      );
    };
    xhr.onerror = () => reject(new ApiError({ title: 'No se pudo enviar el fichero', status: 0 }));
    xhr.onabort = () => reject(new DOMException('Subida cancelada', 'AbortError'));
    signal.addEventListener('abort', () => xhr.abort());
    const form = new FormData();
    form.append('file', file);
    xhr.send(form);
  });
}

/** Sube un fichero con su progreso (`progress`, `null` si no hay subida) y la opción de cancelarlo (`cancel`). */
export function useUploadFile(projectId: number) {
  const queryClient = useQueryClient();
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const controller = useRef<AbortController | null>(null);
  const mutation = useMutation({
    mutationFn: async (file: File) => {
      controller.current = new AbortController();
      setProgress({ loaded: 0, total: file.size });
      try {
        return await sendUpload(projectId, file, setProgress, controller.current.signal);
      } finally {
        controller.current = null;
        setProgress(null);
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: uploadsKey(projectId) }),
  });
  return { ...mutation, progress, cancel: () => controller.current?.abort() };
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
