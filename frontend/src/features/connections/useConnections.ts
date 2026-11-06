import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, ensureOk, unwrap } from '../../api/client';
import type { components, paths } from '../../api/schema';
import { type ListState, listQuery } from '../../components/useListState';

export type ConnectionInfo = components['schemas']['ConnectionOut'];
export type ConnectionCreate = components['schemas']['ConnectionCreate'];
export type ConnectionUpdate = components['schemas']['ConnectionUpdate'];
export type ConnectionTest = components['schemas']['ConnectionTestOut'];
export type Readiness = components['schemas']['ReadinessOut'];
export type AllowlistEntry = components['schemas']['AllowlistEntryOut'];

type ConnectionSort = NonNullable<
  NonNullable<paths['/api/v1/connections']['get']['parameters']['query']>['sort']
>;
/** Máximo de la API (`MAX_PAGE_SIZE`): los selectores de conexión necesitan más de una página de la lista. */
export const OPTIONS_PAGE_SIZE = 200;

export function useConnections(list: ListState, pageSize?: number) {
  return useQuery({
    queryKey: ['connections', { ...list, pageSize }],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/connections', {
          params: { query: listQuery<ConnectionSort>(list, pageSize) },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useConnection(id: number) {
  return useQuery({
    queryKey: ['connections', id],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/connections/{connection_id}', { params: { path: { connection_id: id } } }),
      ),
    enabled: Number.isInteger(id) && id > 0,
  });
}

export function useCreateConnection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: ConnectionCreate) => unwrap(await api.POST('/api/v1/connections', { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['connections'] }),
  });
}

export function useUpdateConnection(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: ConnectionUpdate) =>
      unwrap(
        await api.PATCH('/api/v1/connections/{connection_id}', {
          params: { path: { connection_id: id } },
          body,
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['connections'] }),
  });
}

export function useDeleteConnection(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      ensureOk(
        await api.DELETE('/api/v1/connections/{connection_id}', { params: { path: { connection_id: id } } }),
      ),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ['connections', id] });
      return queryClient.invalidateQueries({ queryKey: ['connections'] });
    },
  });
}

export function useTestConnection(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST('/api/v1/connections/{connection_id}/test', {
          params: { path: { connection_id: id } },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['connections'] }),
  });
}

/** Readiness bajo demanda: conecta con la BD, así que solo se pide al pulsar el botón. */
export function useReadiness(id: number, enabled: boolean) {
  return useQuery({
    queryKey: ['connections', id, 'readiness'],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/connections/{connection_id}/readiness', {
          params: { path: { connection_id: id } },
        }),
      ),
    enabled,
    staleTime: Infinity,
    retry: false,
  });
}

export function useAllowlist() {
  return useQuery({
    queryKey: ['allowlist'],
    queryFn: async () => unwrap(await api.GET('/api/v1/admin/allowlist')),
  });
}

export function useAddAllowlistEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: components['schemas']['AllowlistEntryIn']) =>
      unwrap(await api.POST('/api/v1/admin/allowlist', { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['allowlist'] }),
  });
}

export function useDeleteAllowlistEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (entry: AllowlistEntry) =>
      ensureOk(
        await api.DELETE('/api/v1/admin/allowlist/{entry_id}', { params: { path: { entry_id: entry.id } } }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['allowlist'] }),
  });
}

/** Resumen legible del destino: `host:puerto/bd`, el DSN o el fichero. */
export function targetSummary(connection: Pick<ConnectionInfo, 'db_type' | 'params'>): string {
  const p = connection.params as Record<string, unknown>;
  const text = (key: string) => (p[key] === undefined || p[key] === null ? '' : String(p[key]));
  if (connection.db_type === 'sqlite') return text('database');
  if (connection.db_type === 'hsqldb') return text('jdbc_url');
  if (text('dsn')) return text('dsn');
  const host = text('host') + (text('port') ? `:${text('port')}` : '');
  const db = text('database') || text('service_name') || text('sid');
  return [host, db].filter(Boolean).join('/');
}
