import { useQuery } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type HealthStatus = components['schemas']['HealthStatus'];

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: async (): Promise<HealthStatus> => unwrap(await api.GET('/api/health')),
    refetchInterval: 60_000,
  });
}
