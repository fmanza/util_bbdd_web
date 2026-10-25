import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, ensureOk, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type StorageSettings = components['schemas']['StorageSettingsOut'];
export type StorageUpdate = components['schemas']['StorageUpdate'];
export type StorageKey = keyof StorageSettings;
export type PurgePreview = components['schemas']['PurgePreviewOut'];
export type Usage = components['schemas']['UsageOut'];
export type MyStorage = components['schemas']['MyStorageOut'];

export const USAGE_PAGE_SIZE = 50;
const settingsKey = ['admin', 'storage'] as const;

export function useStorageSettings() {
  return useQuery({
    queryKey: settingsKey,
    queryFn: async () => unwrap(await api.GET('/api/v1/admin/storage')),
  });
}

/** Guarda los ajustes (`null` = volver a la variable `UBW_*`); el uso depende de la cuota: se refresca también. */
export function useUpdateStorage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: StorageUpdate) => unwrap(await api.PATCH('/api/v1/admin/storage', { body })),
    onSuccess: (data) => {
      queryClient.setQueryData(settingsKey, data);
      return queryClient.invalidateQueries({ queryKey: [...settingsKey, 'usage'] });
    },
  });
}

/** Qué purgaría la siguiente pasada con esos ajustes (no borra nada). */
export function usePreviewStorage() {
  return useMutation({
    mutationFn: async (body: StorageUpdate) =>
      unwrap(await api.POST('/api/v1/admin/storage/preview', { body })),
  });
}

export function useRequestMaintenance() {
  return useMutation({
    mutationFn: async () => ensureOk(await api.POST('/api/v1/admin/storage/maintenance')),
  });
}

export function useStorageUsage(q: string, page: number) {
  return useQuery({
    queryKey: [...settingsKey, 'usage', { q, page }],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/admin/storage/usage', {
          params: { query: { q: q || null, limit: USAGE_PAGE_SIZE, offset: (page - 1) * USAGE_PAGE_SIZE } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useMyStorage() {
  return useQuery({
    queryKey: ['me', 'storage'],
    queryFn: async () => unwrap(await api.GET('/api/v1/auth/me/storage')),
  });
}
