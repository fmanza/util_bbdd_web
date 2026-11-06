import { Center, Loader, Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { useListState } from '../../components/useListState';
import { RunsTable } from './RunsTable';
import { useMyRuns } from './useRuns';

/** Ejecuciones recientes de todos mis proyectos. */
export function RunsPage() {
  const { t } = useTranslation();
  const list = useListState();
  const { data, isPending, isError, error } = useMyRuns(list.state);

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
      {data && (
        <RunsTable
          runs={data.items}
          total={data.total}
          showProject
          label={t('runs.title')}
          empty={t('runs.empty')}
          {...list.table}
        />
      )}
    </Stack>
  );
}
