import { Badge } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import type { RunStatus } from './useRuns';

const COLORS: Record<RunStatus, string> = {
  queued: 'gray',
  running: 'blue',
  succeeded: 'green',
  failed: 'red',
  cancelled: 'orange',
  purged: 'dark',
};

export function RunStatusBadge({ status }: { status: RunStatus }) {
  const { t } = useTranslation();
  return (
    <Badge color={COLORS[status]} variant={status === 'running' ? 'filled' : 'light'}>
      {t(`runs.status.${status}`)}
    </Badge>
  );
}
