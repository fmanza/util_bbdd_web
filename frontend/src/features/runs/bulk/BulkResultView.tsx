import { Alert, Anchor, Card, Group, Loader, SimpleGrid, Stack, Table, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { isApiError } from '../../../api/client';
import { ErrorAlert } from '../../../components/ErrorAlert';
import { type BulkResult, useBulkResult } from '../../bulk/useBulk';
import { isActive, type RunDetail } from '../useRuns';

/**
 * Filas que la carga cambió en el destino. `committed` de util_bbdd cuenta las enviadas, también las apartadas (G37):
 * en un insert o un borrado manda el recuento de la tabla; en una actualización, las enviadas menos las apartadas.
 * Sin recuento posterior (`target_rows_after` null), las enviadas menos las apartadas en cualquier operación.
 */
function appliedRows(data: BulkResult): number {
  if (data.target_rows_after === null) return (data.committed ?? 0) - (data.rejected ?? 0);
  if (data.operation === 'insert') return data.target_rows_after - data.target_rows_before;
  if (data.operation === 'delete') return data.target_rows_before - data.target_rows_after;
  return (data.committed ?? 0) - (data.rejected ?? 0);
}

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

/**
 * Resultado de una carga bulk (`bulk_apply`): filas aplicadas en el destino, recuento antes y después, rechazos (con
 * aviso si se apartaron todas) y particiones (Fase 9).
 */
export function BulkResultView({ run }: { run: RunDetail }) {
  const { t } = useTranslation();
  const finished = !isActive(run.status) && run.status !== 'purged';
  const result = useBulkResult(run.id, finished);
  const previewId = String(run.params['preview_run']);
  const data = result.data;
  const allRejected = Boolean(data && data.rows > 0 && (data.rejected ?? 0) === data.rows);

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
            <SimpleGrid cols={{ base: 2, sm: 5 }}>
              <Stat label={t('bulk.result.rows')} value={data.rows} />
              <Stat label={t(`bulk.result.applied.${data.operation}`)} value={appliedRows(data)} />
              <Stat label={t('bulk.result.before')} value={data.target_rows_before} />
              <Stat label={t('bulk.result.after')} value={data.target_rows_after ?? '—'} />
              <Stat label={t('bulk.result.rejected')} value={data.rejected ?? 0} />
            </SimpleGrid>
            <Text size="xs" c="dimmed">
              {t('bulk.result.committedHelp')}
            </Text>
            {data.verified === false && data.target_rows_after !== null && (
              <Alert color="orange" title={t('bulk.result.mismatchTitle')}>
                {t(`bulk.result.mismatch.${data.operation}`, {
                  committed: data.committed ?? 0,
                  matches: data.matches ?? 0,
                  delta: Math.abs(data.target_rows_after - data.target_rows_before),
                })}
              </Alert>
            )}
            {data.target_rows_after === null && (
              <Alert color="yellow" title={t('bulk.result.uncountedTitle')}>
                {t('bulk.result.uncounted')}
              </Alert>
            )}
            {data.cancelled && (
              <Alert color="orange" title={t('bulk.result.cancelledTitle')}>
                {data.committed
                  ? t('bulk.result.cancelledPartial', { count: data.committed })
                  : t('bulk.result.cancelledUndone')}
              </Alert>
            )}
            {data.error && (
              <Alert color="red" title={t('bulk.result.errorTitle')}>
                {data.error}
              </Alert>
            )}
            {allRejected && (
              <Alert color="orange" title={t('bulk.result.allRejectedTitle')}>
                {t('bulk.result.allRejected', { count: data.rows })}
              </Alert>
            )}
            {(data.rejected ?? 0) > 0 && !allRejected && (
              <Alert color="yellow" title={t('bulk.result.rejectsTitle')}>
                {t('bulk.result.rejects')}
              </Alert>
            )}
            {(data.pk_sync ?? []).length > 0 && (
              <Table striped withTableBorder aria-label={t('bulk.result.pkSync')}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{t('bulk.result.pkSyncColumn')}</Table.Th>
                    <Table.Th>{t('bulk.result.pkSyncMax')}</Table.Th>
                    <Table.Th>{t('bulk.result.pkSyncState')}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {(data.pk_sync ?? []).map((s) => (
                    <Table.Tr key={s.column}>
                      <Table.Td>{s.column}</Table.Td>
                      <Table.Td>{s.max_value ?? '—'}</Table.Td>
                      <Table.Td>
                        <Text size="sm" {...(s.status === 'error' ? { c: 'red' } : {})}>
                          {t(`bulk.result.pkSyncStatus.${s.status}`)}
                          {s.error ? `: ${s.error}` : ''}
                        </Text>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
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
