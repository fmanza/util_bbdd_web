import { Alert, Anchor, Badge, Card, Group, List, Loader, Stack, Table, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { isApiError } from '../../../api/client';
import { ErrorAlert } from '../../../components/ErrorAlert';
import { isActive, type RunDetail } from '../useRuns';
import { FkMismatches } from './PlanViewer';
import { useMigrationReport } from './useMigrate';

/** Resultado de una ejecución `migrate_apply`: conflictos, FK, vistas y sentencias aplicadas (Fase 7). */
export function MigrationReportView({ run }: { run: RunDetail }) {
  const { t } = useTranslation();
  const finished = !isActive(run.status) && run.status !== 'purged';
  const report = useMigrationReport(run.id, finished);
  const mode = String(run.params['mode']);
  const planId = String(run.params['plan_run']);

  return (
    <Card withBorder>
      <Stack>
        <Group justify="space-between">
          <Title order={3}>{t(`migrate.report.title.${mode}`)}</Title>
          <Anchor component={Link} to={`/runs/${planId}`} size="sm">
            {t('migrate.report.plan')}
          </Anchor>
        </Group>
        <Text size="sm">
          {t('migrate.report.target', { target: String(run.params['target_connection']) })}
        </Text>
        {!finished && (
          <Text size="sm" c="dimmed">
            {t('migrate.report.pending')}
          </Text>
        )}
        {report.isPending && finished && <Loader size="sm" aria-label={t('common.loading')} />}
        {report.isError && !isApiError(report.error, 404) && <ErrorAlert error={report.error} />}
        {report.data && (
          <Stack>
            {report.data.conflicts && report.data.conflicts.length > 0 && (
              <Alert color="red" title={t('migrate.report.conflictsTitle')}>
                <Text size="sm">{t('migrate.report.conflicts')}</Text>
                <List size="sm">
                  {report.data.conflicts.map((name) => (
                    <List.Item key={name}>{name}</List.Item>
                  ))}
                </List>
              </Alert>
            )}
            <FkMismatches
              items={report.data.fk_mismatches ?? []}
              blocking={report.data.fk_blocking ?? false}
            />
            {report.data.views && report.data.views.length > 0 && (
              <Table striped withTableBorder aria-label={t('migrate.report.views')}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{t('migrate.report.view')}</Table.Th>
                    <Table.Th>{t('migrate.report.validation')}</Table.Th>
                    <Table.Th>{t('migrate.report.detail')}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {report.data.views.map((v) => (
                    <Table.Tr key={v.view}>
                      <Table.Td>{v.view}</Table.Td>
                      <Table.Td>
                        <Badge color={v.valid === false ? 'red' : v.valid ? 'green' : 'gray'} variant="light">
                          {t(`migrate.report.valid.${String(v.valid)}`)}
                        </Badge>
                      </Table.Td>
                      <Table.Td>{v.error ?? v.method}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
            {report.data.mode === 'apply' && (
              <Text size="sm">
                {t('migrate.report.applied', { applied: report.data.applied, total: report.data.statements })}
              </Text>
            )}
            {report.data.cancelled && (
              <Alert color="orange" title={t('migrate.report.cancelledTitle')}>
                {t('migrate.report.cancelled', {
                  applied: report.data.applied,
                  total: report.data.statements,
                })}
              </Alert>
            )}
            {report.data.error && (
              <Alert
                color="red"
                title={t('migrate.report.failedTitle', { n: report.data.failed_position ?? '?' })}
              >
                <Stack gap={4}>
                  {report.data.failed_statement && (
                    <Text size="sm" ff="monospace">
                      {report.data.failed_statement}
                    </Text>
                  )}
                  <Text size="sm">{report.data.error}</Text>
                  <Text size="sm">{t('migrate.report.partial')}</Text>
                </Stack>
              </Alert>
            )}
            {mode === 'dry_run' && run.status === 'succeeded' && (
              <Alert color="green" title={t('migrate.report.dryOkTitle')}>
                {t('migrate.report.dryOk')}
              </Alert>
            )}
          </Stack>
        )}
      </Stack>
    </Card>
  );
}
