import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, ensureOk, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type SchemaList = components['schemas']['SchemaList'];
export type SchemaSummary = components['schemas']['SchemaSummary'];
export type TableDetail = components['schemas']['TableDetail'];
export type ObjectKind = components['schemas']['DdlOut']['kind'];
export type QueryResult = components['schemas']['QueryResultOut'];
export type NamedQuery = components['schemas']['NamedQueryOut'];
export type SqlCapabilities = components['schemas']['SqlCapabilities'];

const key = (connectionId: number) => ['connections', connectionId, 'metadata'] as const;

export function useSchemas(connectionId: number, enabled = true) {
  return useQuery({
    queryKey: [...key(connectionId), 'schemas'],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/connections/{connection_id}/metadata/schemas', {
          params: { path: { connection_id: connectionId } },
        }),
      ),
    enabled,
    staleTime: 5 * 60_000,
    retry: false,
  });
}

export function useSchemaTree(connectionId: number, schema: string | null) {
  return useQuery({
    queryKey: [...key(connectionId), 'tree', schema],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/connections/{connection_id}/metadata/schemas/{schema}', {
          params: { path: { connection_id: connectionId, schema: schema ?? '' } },
        }),
      ),
    enabled: Boolean(schema),
    staleTime: Infinity,
    retry: false,
  });
}

/** Vuelve a leer el catálogo del schema (invalida la caché del servidor y la del navegador). */
export function useRefreshSchema(connectionId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (schema: string) =>
      ensureOk(
        await api.DELETE('/api/v1/connections/{connection_id}/metadata/schemas/{schema}', {
          params: { path: { connection_id: connectionId, schema } },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key(connectionId) }),
  });
}

export function useTable(connectionId: number, schema: string | null, table: string | null) {
  return useQuery({
    queryKey: [...key(connectionId), 'table', schema, table],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/connections/{connection_id}/metadata/schemas/{schema}/tables/{table}', {
          params: { path: { connection_id: connectionId, schema: schema ?? '', table: table ?? '' } },
        }),
      ),
    enabled: Boolean(schema && table),
    staleTime: Infinity,
    retry: false,
  });
}

export function useDdl(
  connectionId: number,
  schema: string | null,
  kind: ObjectKind,
  name: string | null,
  enabled: boolean,
) {
  return useQuery({
    queryKey: [...key(connectionId), 'ddl', schema, kind, name],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/connections/{connection_id}/metadata/schemas/{schema}/ddl', {
          params: {
            path: { connection_id: connectionId, schema: schema ?? '' },
            query: { kind, name: name ?? '' },
          },
        }),
      ),
    enabled: enabled && Boolean(schema && name),
    staleTime: Infinity,
    retry: false,
  });
}

export function useConnectionQueries(connectionId: number) {
  return useQuery({
    queryKey: ['connections', connectionId, 'queries'],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/connections/{connection_id}/queries', {
          params: { path: { connection_id: connectionId } },
        }),
      ),
  });
}

export function useRunNamedQuery(connectionId: number) {
  return useMutation({
    mutationFn: async ({
      queryId,
      params,
      limit,
    }: {
      queryId: number;
      params: Record<string, string>;
      limit: number | null;
    }) =>
      unwrap(
        await api.POST('/api/v1/connections/{connection_id}/queries/{query_id}/run', {
          params: { path: { connection_id: connectionId, query_id: queryId } },
          body: { params, limit },
        }),
      ),
  });
}

export function useSqlCapabilities(projectId: number) {
  return useQuery({
    queryKey: ['projects', projectId, 'sql'],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/sql', { params: { path: { project_id: projectId } } }),
      ),
  });
}

export function useRunSql(projectId: number) {
  return useMutation({
    mutationFn: async ({ alias, sql, limit }: { alias: string; sql: string; limit: number | null }) =>
      unwrap(
        await api.POST('/api/v1/projects/{project_id}/connections/{alias}/sql', {
          params: { path: { project_id: projectId, alias } },
          body: { sql, limit },
        }),
      ),
  });
}

export function useAdminQueries() {
  return useQuery({
    queryKey: ['admin', 'queries'],
    queryFn: async () => unwrap(await api.GET('/api/v1/admin/queries')),
  });
}

export function useSaveQuery() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      body,
    }: {
      id: number | null;
      body: components['schemas']['NamedQueryCreate'];
    }) =>
      id === null
        ? unwrap(await api.POST('/api/v1/admin/queries', { body }))
        : unwrap(
            await api.PATCH('/api/v1/admin/queries/{query_id}', {
              params: { path: { query_id: id } },
              body: { name: body.name, description: body.description, sql_template: body.sql_template },
            }),
          ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'queries'] }),
  });
}

export function useDeleteQuery() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      ensureOk(await api.DELETE('/api/v1/admin/queries/{query_id}', { params: { path: { query_id: id } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'queries'] }),
  });
}
