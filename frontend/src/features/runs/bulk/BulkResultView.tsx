import { Alert, Anchor, Card, Group, Loader, SimpleGrid, Stack, Table, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { isApiError } from '../../../api/client';
import { ErrorAlert } from '../../../components/ErrorAlert';
import { useBulkResult } from '../../bulk/useBulk';
import { isActive, type RunDetail } from '../useRuns';

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <Card withBorder padding="sm">
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text fw={700} size="xl">
        {value}
      </Text>
    </Card>
  );
}

/** Resultado de una carga bulk (`bulk_apply`): filas antes y después, rechazos y particiones (Fase 9). */
export function BulkResultView({ run }: { run: RunDetail }) {
  const { t } = useTranslation();
  const finished = !isActive(run.status) && run.status !== 'purged';
  const result = useBulkResult(run.id, finished);
  const previewId = String(run.params['preview_run']);
  const data = result.data;

  return (
    <Card withBorder>
      <Stack>
        <Group justify="space-between">
          <Title order={3}>{t('bulk.result.title')}</Title>
          <Anchor component={Link} to={`/runs/${previewId}`} size="sm">
            {t('bulk.result.preview')}
          </Anchor>
        </Group>
        {!finished && (
          <Text size="sm" c="dimmed">
            {t('bulk.result.pending')}
          </Text>
        )}
        {result.isPending && finished && <Loader size="sm" aria-label={t('common.loading')} />}
        {result.isError && !isApiError(result.error, 404) && <ErrorAlert error={result.error} />}
        {data && (
          <>
            <SimpleGrid cols={{ base: 2, sm: 4 }}>
              <Stat label={t('bulk.result.rows')} value={data.rows} />
              <Stat label={t('bulk.result.before')} value={data.target_rows_before} />
              <Stat label={t('bulk.result.after')} value={data.target_rows_after} />
              <Stat label={t('bulk.result.rejected')} value={data.rejected ?? 0} />
            </SimpleGrid>
            {data.error && (
              <Alert color="red" title={t('bulk.result.errorTitle')}>
                {data.error}
              </Alert>
            )}
            {(data.rejected ?? 0) > 0 && (
              <Alert color="yellow" title={t('bulk.result.rejectsTitle')}>
                {t('bulk.result.rejects')}
              </Alert>
            )}
            {(data.partitions ?? []).length > 0 && (
              <Table striped withTableBorder aria-label={t('bulk.result.partitions')}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>#</Table.Th>
                    <Table.Th>{t('bulk.result.rows')}</Table.Th>
                    <Table.Th>{t('bulk.result.error')}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {(data.partitions ?? []).map((p) => (
                    <Table.Tr key={p.index}>
                      <Table.Td>{p.index + 1}</Table.Td>
                      <Table.Td>{p.rows}</Table.Td>
                      <Table.Td>{p.error ?? '—'}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
          </>
        )}
      </Stack>
    </Card>
  );
}
