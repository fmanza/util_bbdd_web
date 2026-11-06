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

type Query<P extends keyof paths, M extends 'get'> = NonNullable<
  NonNullable<paths[P][M]> extends { parameters: { query?: infer Q } } ? Q : never
>;
type SortOf<P extends keyof paths> = NonNullable<Query<P, 'get'> extends { sort?: infer S } ? S : never>;

export function useUsers(list: ListState) {
  return useQuery({
    queryKey: ['users', list],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/users', {
          params: { query: listQuery<SortOf<'/api/v1/users'>>(list) },
        }),
      ),
    placeholderData: keepPreviousData,
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
