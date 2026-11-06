import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, ensureOk, unwrap } from '../../api/client';
import type { components, paths } from '../../api/schema';
import { type ListState, listQuery } from '../../components/useListState';

export type StorageSettings = components['schemas']['StorageSettingsOut'];
export type StorageUpdate = components['schemas']['StorageUpdate'];
export type StorageKey = keyof StorageSettings;
export type PurgePreview = components['schemas']['PurgePreviewOut'];
export type Usage = components['schemas']['UsageOut'];
export type MyStorage = components['schemas']['MyStorageOut'];

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

type UsageSort = NonNullable<
  NonNullable<paths['/api/v1/admin/storage/usage']['get']['parameters']['query']>['sort']
>;

export function useStorageUsage(list: ListState) {
  return useQuery({
    queryKey: [...settingsKey, 'usage', list],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/admin/storage/usage', {
          params: { query: listQuery<UsageSort>(list) },
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
