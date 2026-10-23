import {
  Alert,
  Button,
  Card,
  Checkbox,
  Group,
  List,
  Loader,
  Modal,
  NumberInput,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import { ErrorAlert } from '../../../components/ErrorAlert';
import { useMe } from '../../auth/useAuth';
import { type BulkPreview, useBulkPreview } from '../../bulk/useBulk';
import { useProjectConnections } from '../../projects/useProjects';
import { SqlBlock } from '../migrate/SqlBlock';
import { type RunDetail, useArtifactText, useLaunchRun } from '../useRuns';

/** Antigüedad máxima de la vista previa que permite cargar (la API lo vuelve a comprobar). */
const PREVIEW_MAX_AGE_MS = 60 * 60 * 1000;
const SQL_LINES = 200;

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

function ConfirmBulk({
  preview,
  alias,
  opened,
  pending,
  error,
  onClose,
  onConfirm,
}: {
  preview: BulkPreview;
  alias: string;
  opened: boolean;
  pending: boolean;
  error: unknown;
  onClose: () => void;
  onConfirm: (rows: number | null, nonAtomic: boolean) => void;
}) {
  const { t } = useTranslation();
  const [understood, setUnderstood] = useState(false);
  const [typed, setTyped] = useState('');
  const [rows, setRows] = useState<number | string>('');
  const [nonAtomic, setNonAtomic] = useState(false);
  const counted = preview.operation !== 'insert';
  const parallel = preview.parallel.workers > 1;
  const ready =
    understood &&
    typed === alias &&
    (!counted || Number(rows) === preview.matches) &&
    (!parallel || nonAtomic);
  return (
    <Modal opened={opened} onClose={onClose} title={t('bulk.apply.confirmTitle')}>
      <Stack>
        {error !== null && <ErrorAlert error={error} />}
        <Alert
          color="red"
          title={t(`bulk.apply.warning.${preview.operation}`, { count: preview.matches ?? 0 })}
        >
          {t('bulk.apply.noCancel', { alias })}
        </Alert>
        <Checkbox
          label={t('bulk.apply.understand')}
          checked={understood}
          onChange={(event) => setUnderstood(event.currentTarget.checked)}
        />
        {parallel && (
          <Checkbox
            label={t('bulk.apply.nonAtomic', { workers: preview.parallel.workers })}
            checked={nonAtomic}
            onChange={(event) => setNonAtomic(event.currentTarget.checked)}
          />
        )}
        <TextInput
          label={t('bulk.apply.typeAlias', { alias })}
          value={typed}
          onChange={(event) => setTyped(event.currentTarget.value)}
          autoComplete="off"
        />
        {counted && (
          <NumberInput
            label={t('bulk.apply.typeRows')}
            value={rows}
            onChange={setRows}
            min={0}
            allowDecimal={false}
          />
        )}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            color="red"
            disabled={!ready}
            loading={pending}
            onClick={() => onConfirm(counted ? Number(rows) : null, nonAtomic)}
          >
            {t('bulk.apply.submit')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function ApplyPanel({ run, preview }: { run: RunDetail; preview: BulkPreview }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data: me } = useMe();
  const connections = useProjectConnections(run.project_id);
  const launch = useLaunchRun(run.project_id);
  const [confirming, setConfirming] = useState(false);
  const alias = String(run.params['target_connection']);
  const target = (connections.data ?? []).find((c) => c.alias === alias);
  const allowed = Boolean(me?.can_write_data) && run.my_role === 'owner';
  const finished = run.finished_at ? new Date(run.finished_at).getTime() : 0;
  const stale = connections.dataUpdatedAt - finished > PREVIEW_MAX_AGE_MS;
  const reason = preview.errors.length
    ? t('bulk.apply.hasErrors')
    : !allowed
      ? me?.can_write_data
        ? t('bulk.apply.ownerOnly')
        : t('bulk.apply.noPermission')
      : target?.read_only
        ? t('bulk.apply.readOnly', { alias })
        : stale
          ? t('bulk.apply.stale')
          : null;

  return (
    <Stack>
      <Title order={4}>{t('bulk.apply.title')}</Title>
      {reason ? (
        <Text size="sm" c="dimmed">
          {reason}
        </Text>
      ) : (
        <Group>
          <Button color="red" onClick={() => setConfirming(true)}>
            {t(`bulk.apply.open.${preview.operation}`, { alias })}
          </Button>
          <ConfirmBulk
            preview={preview}
            alias={alias}
            opened={confirming}
            pending={launch.isPending}
            error={confirming && launch.isError ? launch.error : null}
            onClose={() => {
              setConfirming(false);
              launch.reset();
            }}
            onConfirm={(rows, nonAtomic) =>
              launch.mutate(
                {
                  operation: 'bulk_apply',
                  params: {
                    preview_run: run.id,
                    confirm: alias,
                    ...(rows !== null ? { confirm_rows: rows } : {}),
                    ...(nonAtomic ? { accept_non_atomic: true } : {}),
                  },
                },
                { onSuccess: (created) => void navigate(`/runs/${created.id}`) },
              )
            }
          />
        </Group>
      )}
    </Stack>
  );
}

function GeneratedSql({ run, file }: { run: RunDetail; file: string }) {
  const { t } = useTranslation();
  const artifact = run.artifacts.find((a) => a.path === `outputs/${file}`) ?? null;
  const text = useArtifactText(run.id, artifact);
  if (!artifact) return null;
  if (text.isPending) return <Loader size="sm" aria-label={t('common.loading')} />;
  if (text.isError) return <Text c="dimmed">{t('bulk.preview.sqlTooBig')}</Text>;
  const lines = text.data.split('\n');
  return (
    <Stack gap={4}>
      <SqlBlock code={lines.slice(0, SQL_LINES).join('\n')} label={t('bulk.preview.sql')} />
      {lines.length > SQL_LINES && (
        <Text size="xs" c="dimmed">
          {t('bulk.preview.sqlMore', { count: lines.length - SQL_LINES })}
        </Text>
      )}
    </Stack>
  );
}

/** Vista previa (modo seco) de una carga bulk y panel para ejecutarla (Fase 9, ADR-010). */
export function BulkPreviewViewer({ run }: { run: RunDetail }) {
  const { t } = useTranslation();
  const preview = useBulkPreview(run.id);
  const data = preview.data;
  return (
    <Card withBorder>
      <Stack>
        <Title order={3}>{t('bulk.preview.title')}</Title>
        {preview.isPending && <Loader size="sm" aria-label={t('common.loading')} />}
        {preview.isError && <ErrorAlert error={preview.error} />}
        {data && (
          <>
            <Text size="sm">
              {t('bulk.preview.route', {
                operation: t(`bulk.operations.${data.operation}`),
                file: data.upload_filename ?? '',
                table: data.schema ? `${data.schema}.${data.table}` : data.table,
                target: String(run.params['target_connection']),
              })}
            </Text>
            <SimpleGrid cols={{ base: 2, sm: 4 }}>
              <Stat label={t('bulk.preview.rows')} value={data.rows} />
              <Stat label={t('bulk.preview.targetRows')} value={data.target_rows} />
              <Stat
                label={t(`bulk.preview.matches.${data.operation}`)}
                value={data.matches === null || data.matches === undefined ? '—' : data.matches}
              />
              <Stat label={t('bulk.preview.workers')} value={data.parallel.workers} />
            </SimpleGrid>
            {data.errors.length > 0 && (
              <Alert color="red" title={t('bulk.preview.errorsTitle')}>
                <List size="sm">
                  {data.errors.map((e) => (
                    <List.Item key={e}>{e}</List.Item>
                  ))}
                </List>
              </Alert>
            )}
            {data.ignored_columns && data.ignored_columns.length > 0 && (
              <Text size="sm" c="dimmed">
                {t('bulk.preview.ignored', { columns: data.ignored_columns.join(', ') })}
              </Text>
            )}
            {data.parallel.workers > 1 && (
              <Alert
                color="yellow"
                title={t('bulk.preview.parallelTitle', { workers: data.parallel.workers })}
              >
                {(data.parallel.reasons ?? []).join(' · ')}
              </Alert>
            )}
            <Table striped withTableBorder aria-label={t('bulk.preview.sample')}>
              <Table.Thead>
                <Table.Tr>
                  {data.columns.map((c) => (
                    <Table.Th key={c}>{c}</Table.Th>
                  ))}
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {data.sample.map((row, index) => (
                  <Table.Tr key={index}>
                    {row.map((value, column) => (
                      <Table.Td key={column}>{value ?? '—'}</Table.Td>
                    ))}
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
            {data.sql_file && <GeneratedSql run={run} file={data.sql_file} />}
            <ApplyPanel run={run} preview={data} />
          </>
        )}
      </Stack>
    </Card>
  );
}
