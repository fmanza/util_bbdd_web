import { Center, Loader, Pagination, Stack, Text, Title } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { RunsTable } from './RunsTable';
import { PAGE_SIZE, useMyRuns } from './useRuns';

/** Ejecuciones recientes de todos mis proyectos. */
export function RunsPage() {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const { data, isPending, isError, error } = useMyRuns(page);

  return (
    <Stack>
      <Title order={2}>{t('runs.title')}</Title>
      <Text c="dimmed">{t('runs.intro')}</Text>
      {isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {isError && <ErrorAlert error={error} />}
      {data && data.items.length === 0 && <Text c="dimmed">{t('runs.empty')}</Text>}
      {data && data.items.length > 0 && <RunsTable runs={data.items} showProject />}
      {data && data.total > PAGE_SIZE && (
        <Pagination total={Math.ceil(data.total / PAGE_SIZE)} value={page} onChange={setPage} />
      )}
    </Stack>
  );
}
