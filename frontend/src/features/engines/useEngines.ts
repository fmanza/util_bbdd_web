import { useQuery } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type Engine = components['schemas']['EngineOut'];
export type EngineDetail = components['schemas']['EngineDetailOut'];
export type EngineParam = components['schemas']['ParamOut'];

// El catálogo solo cambia con la versión de util_bbdd: se cachea durante la sesión.
const CATALOG_STALE_TIME = 60 * 60_000;

export function useEngines() {
  return useQuery({
    queryKey: ['engines'],
    queryFn: async () => unwrap(await api.GET('/api/v1/engines')),
    staleTime: CATALOG_STALE_TIME,
  });
}

export function useEngine(dbType: string | null | undefined) {
  return useQuery({
    queryKey: ['engines', dbType],
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/engines/{db_type}', { params: { path: { db_type: dbType ?? '' } } })),
    enabled: Boolean(dbType),
    staleTime: CATALOG_STALE_TIME,
  });
}
