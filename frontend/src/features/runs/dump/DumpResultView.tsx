import { Alert, Anchor, Badge, Card, Group, List, Loader, Stack, Table, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { isApiError } from '../../../api/client';
import { ErrorAlert } from '../../../components/ErrorAlert';
import { isActive, type RunDetail } from '../useRuns';
import { type DumpResult, useDumpResult } from './useDump';

const STATUS_COLORS: Record<string, string> = {
  success: 'green',
  missing_target: 'gray',
  skipped: 'gray',
  error: 'red',
  enabled: 'green',
  failed: 'red',
  unverified: 'yellow',
};

const statusColor = (status: string): string => STATUS_COLORS[status] ?? 'gray';

function Constraints({ result }: { result: DumpResult }) {
  const { t } = useTranslation();
  const problems = (result.constraints ?? []).filter((c) => c.status !== 'enabled');
  if (problems.length === 0) return null;
  return (
    <Alert
      color={problems.some((c) => c.status === 'failed') ? 'red' : 'yellow'}
      title={t('dump.result.constraints')}
    >
      <Table withTableBorder aria-label={t('dump.result.constraints')}>
        <Table.Tbody>
          {problems.map((c) => (
            <Table.Tr key={`${c.table}.${c.constraint}`}>
              <Table.Td>
                {c.table}.{c.constraint}
              </Table.Td>
              <Table.Td>
                <Badge color={statusColor(c.status)} variant="light">
                  {t(`dump.result.constraintStatus.${c.status}`)}
                </Badge>
              </Table.Td>
              <Table.Td>{c.error}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Alert>
  );
}

/** Resultado de un volcado (`dump_apply`): filas por tabla, rechazos y constraints (Fase 8). */
export function DumpResultView({ run }: { run: RunDetail }) {
  const { t } = useTranslation();
  const finished = !isActive(run.status) && run.status !== 'purged';
  const result = useDumpResult(run.id, finished);
  const previewId = String(run.params['preview_run']);
  const rejects = run.artifacts.find((a) => a.kind === 'rejects');

  return (
    <Card withBorder>
      <Stack>
        <Group justify="space-between">
          <Title order={3}>{t('dump.result.title')}</Title>
          <Anchor component={Link} to={`/runs/${previewId}`} size="sm">
            {t('dump.result.preview')}
          </Anchor>
        </Group>
        {!finished && (
          <Text size="sm" c="dimmed">
            {t('dump.result.pending')}
          </Text>
        )}
        {result.isPending && finished && <Loader size="sm" aria-label={t('common.loading')} />}
        {result.isError && !isApiError(result.error, 404) && <ErrorAlert error={result.error} />}
        {result.data && (
          <>
            {result.data.cancelled && (
              <Alert color="orange" title={t('dump.result.cancelledTitle')}>
                <Text size="sm">
                  {t('dump.result.cancelled', { count: (result.data.completed_tables ?? []).length })}
                </Text>
                {(result.data.completed_tables ?? []).length > 0 && (
                  <List size="sm">
                    {(result.data.completed_tables ?? []).map((name) => (
                      <List.Item key={name}>{name}</List.Item>
                    ))}
                  </List>
                )}
              </Alert>
            )}
            <Constraints result={result.data} />
            {rejects && (
              <Alert color="yellow" title={t('dump.result.rejectsTitle')}>
                {t('dump.result.rejects')}
              </Alert>
            )}
            {result.data.tables.length > 0 && (
              <Table striped withTableBorder aria-label={t('dump.result.tables')}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{t('dump.preview.table')}</Table.Th>
                    <Table.Th>{t('runs.statusLabel')}</Table.Th>
                    <Table.Th>{t('dump.result.source')}</Table.Th>
                    <Table.Th>{t('dump.result.before')}</Table.Th>
                    <Table.Th>{t('dump.result.after')}</Table.Th>
                    <Table.Th>{t('dump.result.rejected')}</Table.Th>
                    <Table.Th>{t('dump.result.error')}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {result.data.tables.map((table) => (
                    <Table.Tr key={table.table}>
                      <Table.Td>{table.table}</Table.Td>
                      <Table.Td>
                        <Badge color={statusColor(table.status)} variant="light">
                          {t(`dump.result.status.${table.status}`)}
                        </Badge>
                      </Table.Td>
                      <Table.Td>{table.source_rows}</Table.Td>
                      <Table.Td>{table.target_rows_before}</Table.Td>
                      <Table.Td>{table.target_rows_after}</Table.Td>
                      <Table.Td>{table.rows_rejected || ''}</Table.Td>
                      <Table.Td>{table.error}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
            {!result.data.report && !result.data.cancelled && (
              <Text size="sm" c="dimmed">
                {t('dump.result.noReport')}
              </Text>
            )}
          </>
        )}
      </Stack>
    </Card>
  );
}
