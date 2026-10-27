import {
  Alert,
  Anchor,
  Button,
  Card,
  Center,
  Code,
  Group,
  List,
  Loader,
  Modal,
  Progress,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatBytes, formatDateTime, formatDuration } from '../../components/format';
import { canRole } from '../projects/useProjects';
import { ArtifactBrowser } from './ArtifactBrowser';
import { BulkPreviewViewer } from './bulk/BulkPreviewViewer';
import { BulkResultView } from './bulk/BulkResultView';
import { DiffViewer } from './compare/DiffViewer';
import { DumpPreviewViewer } from './dump/DumpPreviewViewer';
import { DumpResultView } from './dump/DumpResultView';
import { MigrationReportView } from './migrate/MigrationReportView';
import { PlanViewer } from './migrate/PlanViewer';
import { RunOutputs } from './RunOutputs';
import { RunStatusBadge } from './RunStatusBadge';
import { archiveUrl, isActive, useCancelRun, usePurgeRun, useRelaunchRun, useLiveRun } from './useRuns';

/** Operaciones que no se relanzan (la API responde 409): aplicar una migración exige un modo seco nuevo. */
const NOT_RELAUNCHABLE = new Set(['migrate_apply', 'dump_apply', 'bulk_apply', 'dump_restore']);
/** Escrituras que en curso paran entre pasos (sentencias, lotes): se confirma antes (ADR-008/009/010). */
const CANCEL_BETWEEN_STEPS: Record<string, 'migrate' | 'dump' | 'bulk'> = {
  migrate_apply: 'migrate',
  dump_apply: 'dump',
  bulk_apply: 'bulk',
};
/** Textos del modal de confirmación de cada una. */
const CANCEL_TEXTS = {
  migrate: {
    title: 'runs.cancelApplyTitle',
    body: 'runs.cancelApplyBody',
    keep: 'runs.keepRunning',
    stop: 'runs.cancelApply',
  },
  dump: {
    title: 'runs.cancelDumpTitle',
    body: 'runs.cancelDumpBody',
    keep: 'runs.keepDumping',
    stop: 'runs.cancelDump',
  },
  bulk: {
    title: 'runs.cancelBulkTitle',
    body: 'runs.cancelBulkBody',
    keep: 'runs.keepLoading',
    stop: 'runs.cancelBulk',
  },
} as const;

export function RunDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const runId = useParams().runId ?? '';
  const { data: run, isPending, isError, error, polling } = useLiveRun(runId);
  const cancel = useCancelRun(runId);
  const relaunch = useRelaunchRun(runId);
  const purge = usePurgeRun(runId);
  const [confirmPurge, setConfirmPurge] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);

  if (isPending) {
    return (
      <Center>
        <Loader aria-label={t('common.loading')} />
      </Center>
    );
  }
  if (isError) {
    return <ErrorAlert error={error} />;
  }

  const editor = canRole(run.my_role, 'editor');
  const active = isActive(run.status);
  // Aplicar una migración, volcar o cargar datos se cancela solo entre pasos: se confirma antes.
  const stepKind =
    run.status === 'running' && (run.operation !== 'migrate_apply' || run.params['mode'] === 'apply')
      ? CANCEL_BETWEEN_STEPS[run.operation]
      : undefined;
  const cancelTexts = CANCEL_TEXTS[stepKind ?? 'migrate'];
  const params = Object.entries(run.params);

  return (
    <Stack maw={1100}>
      <Group justify="space-between">
        <Stack gap={2}>
          <Title order={2}>{t('runs.detailTitle', { operation: run.operation })}</Title>
          <Text size="sm" c="dimmed">
            <Anchor component={Link} to={`/projects/${run.project_id}`}>
              {run.project_name}
            </Anchor>{' '}
            · <Code>{run.id}</Code>
          </Text>
        </Stack>
        <Group gap="xs">
          {editor && active && (
            <Button
              color="orange"
              variant="light"
              onClick={() => (stepKind ? setConfirmCancel(true) : cancel.mutate())}
              loading={cancel.isPending}
              disabled={run.cancel_requested}
            >
              {run.cancel_requested ? t('runs.cancelling') : t('runs.cancel')}
            </Button>
          )}
          {editor && !active && run.status !== 'purged' && !NOT_RELAUNCHABLE.has(run.operation) && (
            <Button
              variant="light"
              loading={relaunch.isPending}
              onClick={() =>
                relaunch.mutate(undefined, { onSuccess: (next) => void navigate(`/runs/${next.id}`) })
              }
            >
              {t('runs.relaunch')}
            </Button>
          )}
          {run.artifacts.length > 0 && (
            <Button component="a" href={archiveUrl(run.id)} variant="default">
              {t('runs.downloadZip')}
            </Button>
          )}
          {editor && !active && run.status !== 'purged' && (
            <Button color="red" variant="subtle" onClick={() => setConfirmPurge(true)}>
              {t('runs.purge')}
            </Button>
          )}
        </Group>
      </Group>
      {(cancel.isError || relaunch.isError || purge.isError) && (
        <ErrorAlert error={cancel.error ?? relaunch.error ?? purge.error} />
      )}

      <Card withBorder>
        <Stack gap="xs" aria-live="polite" aria-atomic="true">
          <Group>
            <RunStatusBadge status={run.status} />
            <Text size="sm">
              {run.progress_message ??
                t(`runs.phases.${run.phase ?? 'queued'}`, { defaultValue: run.phase ?? '' })}
            </Text>
          </Group>
          {(active || run.progress_pct !== null) && (
            <Progress
              value={run.progress_pct ?? 0}
              animated={run.status === 'running'}
              aria-label={t('runs.progressLabel', { pct: run.progress_pct ?? 0 })}
            />
          )}
          {run.error_message && (
            <Alert
              color={run.status === 'cancelled' ? 'orange' : 'red'}
              title={t(`runs.status.${run.status}`)}
            >
              {run.error_message}
            </Alert>
          )}
          {(run.warnings ?? []).length > 0 && (
            <Alert color="yellow" title={t('runs.warningsTitle')}>
              <List size="sm">
                {(run.warnings ?? []).map((warning) => (
                  <List.Item key={warning}>{warning}</List.Item>
                ))}
              </List>
            </Alert>
          )}
          {polling && active && (
            <Text size="xs" c="dimmed">
              {t('runs.polling')}
            </Text>
          )}
        </Stack>
      </Card>

      <Table>
        <Table.Tbody>
          <Table.Tr>
            <Table.Th w={200}>{t('runs.user')}</Table.Th>
            <Table.Td>{run.username ?? '—'}</Table.Td>
          </Table.Tr>
          <Table.Tr>
            <Table.Th>{t('runs.createdAt')}</Table.Th>
            <Table.Td>{formatDateTime(run.created_at)}</Table.Td>
          </Table.Tr>
          <Table.Tr>
            <Table.Th>{t('runs.duration')}</Table.Th>
            <Table.Td>{formatDuration(run.duration_seconds)}</Table.Td>
          </Table.Tr>
          <Table.Tr>
            <Table.Th>{t('runs.size')}</Table.Th>
            <Table.Td>{formatBytes(run.size_bytes)}</Table.Td>
          </Table.Tr>
          {run.relaunched_from && (
            <Table.Tr>
              <Table.Th>{t('runs.relaunchedFrom')}</Table.Th>
              <Table.Td>
                <Anchor component={Link} to={`/runs/${run.relaunched_from}`}>
                  <Code>{run.relaunched_from}</Code>
                </Anchor>
              </Table.Td>
            </Table.Tr>
          )}
          {params.map(([name, value]) => (
            <Table.Tr key={name}>
              <Table.Th>
                <Code>{name}</Code>
              </Table.Th>
              <Table.Td>{value === null ? '—' : String(value)}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>

      {run.operation === 'migrate_plan' && run.status === 'succeeded' && <PlanViewer run={run} />}
      {run.operation === 'migrate_apply' && <MigrationReportView run={run} />}
      {run.operation === 'dump_preview' && run.status === 'succeeded' && <DumpPreviewViewer run={run} />}
      {run.operation === 'dump_apply' && <DumpResultView run={run} />}
      {run.operation === 'bulk_preview' && run.status === 'succeeded' && <BulkPreviewViewer run={run} />}
      {run.operation === 'bulk_apply' && <BulkResultView run={run} />}
      {run.operation === 'compare' && run.status === 'succeeded' && (
        <DiffViewer runId={run.id} projectId={run.project_id} />
      )}
      {run.status !== 'purged' && <RunOutputs run={run} />}

      <Title order={3}>{t('runs.artifacts')}</Title>
      {run.status === 'purged' ? (
        <Text c="dimmed">{t('runs.purgedBody')}</Text>
      ) : (
        <ArtifactBrowser runId={run.id} artifacts={run.artifacts} />
      )}

      <Modal
        opened={confirmCancel && stepKind !== undefined}
        onClose={() => setConfirmCancel(false)}
        title={t(cancelTexts.title)}
      >
        <Stack>
          <Text>{t(cancelTexts.body)}</Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setConfirmCancel(false)}>
              {t(cancelTexts.keep)}
            </Button>
            <Button
              color="orange"
              loading={cancel.isPending}
              onClick={() => cancel.mutate(undefined, { onSuccess: () => setConfirmCancel(false) })}
            >
              {t(cancelTexts.stop)}
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal opened={confirmPurge} onClose={() => setConfirmPurge(false)} title={t('runs.purgeTitle')}>
        <Stack>
          <Text>{t('runs.purgeBody', { id: run.id })}</Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setConfirmPurge(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              color="red"
              loading={purge.isPending}
              onClick={() => purge.mutate(undefined, { onSuccess: () => setConfirmPurge(false) })}
            >
              {t('runs.purge')}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
