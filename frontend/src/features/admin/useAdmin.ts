import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, ensureOk, unwrap } from '../../api/client';
import type { components, paths } from '../../api/schema';
import { type ListState, listQuery } from '../../components/useListState';
import { meQueryKey } from '../auth/useAuth';

export type User = components['schemas']['UserOut'];
export type UserCreate = components['schemas']['UserCreate'];
export type UserUpdate = components['schemas']['UserUpdate'];
export type SessionInfo = components['schemas']['SessionOut'];
export type AuditEntry = components['schemas']['AuditEntryOut'];
export type Role = User['role'];
export type UserDeletionCheck = components['schemas']['UserDeletionCheck'];
export type UserTransfer = components['schemas']['UserTransfer'];
export type TransferItem = components['schemas']['TransferItem'];
/** Filtros propios de la lista de usuarios (vacío = todos). */
export interface UserFilters {
  role: Role | '';
  status: 'active' | 'inactive' | 'locked' | '';
}

type Query<P extends keyof paths, M extends 'get'> = NonNullable<
  NonNullable<paths[P][M]> extends { parameters: { query?: infer Q } } ? Q : never
>;
type SortOf<P extends keyof paths> = NonNullable<Query<P, 'get'> extends { sort?: infer S } ? S : never>;

export function useUsers(list: ListState, filters: UserFilters = { role: '', status: '' }) {
  return useQuery({
    queryKey: ['users', list, filters],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/users', {
          params: {
            query: {
              ...listQuery<SortOf<'/api/v1/users'>>(list),
              role: filters.role || null,
              status: filters.status || null,
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

/** Qué impide borrar un usuario (se consulta al abrir la confirmación, nunca en caché). */
export function useDeletionCheck(userId: number) {
  return useQuery({
    // Fuera de ['users']: al borrar se invalida la lista y no debe repetirse la comprobación (daría 404).
    queryKey: ['user-deletion-check', userId],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/users/{user_id}/deletion-check', { params: { path: { user_id: userId } } }),
      ),
    staleTime: 0,
    gcTime: 0,
  });
}

export function useDeleteUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      ensureOk(await api.DELETE('/api/v1/users/{user_id}', { params: { path: { user_id: id } } })),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: ['users'] }),
        queryClient.invalidateQueries({ queryKey: ['sessions'] }),
      ]),
  });
}

/** Usuarios activos que contienen `q` (destino de una transferencia); `q` ya con retardo. */
export function useActiveUserOptions(q: string) {
  return useQuery({
    queryKey: ['users', 'options', q],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/users', {
          params: { query: { q: q.trim() || null, status: 'active', limit: 20, offset: 0 } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

/** Qué movería transferir lo de `userId` a `targetId` (sin caché: cambia con cada proyecto o ejecución). */
export function useTransferPreview(userId: number, targetId: number | null) {
  return useQuery({
    queryKey: ['user-transfer-preview', userId, targetId],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/users/{user_id}/transfer-preview', {
          params: { path: { user_id: userId }, query: { target_user_id: targetId ?? 0 } },
        }),
      ),
    enabled: targetId !== null,
    staleTime: 0,
    gcTime: 0,
  });
}

export function useTransferUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      targetId,
      removeMemberships,
    }: {
      id: number;
      targetId: number;
      removeMemberships: boolean;
    }) =>
      unwrap(
        await api.POST('/api/v1/users/{user_id}/transfer', {
          params: { path: { user_id: id } },
          body: { target_user_id: targetId, remove_memberships: removeMemberships },
        }),
      ),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: ['users'] }),
        queryClient.invalidateQueries({ queryKey: ['user-deletion-check'] }),
        queryClient.invalidateQueries({ queryKey: ['projects'] }),
        queryClient.invalidateQueries({ queryKey: ['connections'] }),
      ]),
  });
}

export function useUnlockUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(await api.POST('/api/v1/users/{user_id}/unlock', { params: { path: { user_id: id } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: UserCreate) => unwrap(await api.POST('/api/v1/users', { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: UserUpdate }) =>
      unwrap(await api.PATCH('/api/v1/users/{user_id}', { params: { path: { user_id: id } }, body })),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: ['users'] }),
        queryClient.invalidateQueries({ queryKey: ['sessions'] }),
      ]),
  });
}

export function useSessions(list: ListState) {
  return useQuery({
    queryKey: ['sessions', list],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/sessions', {
          params: { query: listQuery<SortOf<'/api/v1/sessions'>>(list) },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useRevokeSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (session: SessionInfo) =>
      ensureOk(
        await api.DELETE('/api/v1/sessions/{session_id}', { params: { path: { session_id: session.id } } }),
      ),
    onSuccess: (_data, session) =>
      session.current
        ? queryClient.invalidateQueries({ queryKey: meQueryKey })
        : queryClient.invalidateQueries({ queryKey: ['sessions'] }),
  });
}

export function useAudit(action: string, list: ListState) {
  return useQuery({
    queryKey: ['audit', { action, ...list }],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/audit', {
          params: {
            query: { action: action || null, ...listQuery<SortOf<'/api/v1/audit'>>(list) },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}
