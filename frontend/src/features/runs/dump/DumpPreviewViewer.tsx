import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Checkbox,
  Group,
  List,
  Loader,
  Modal,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';

import { ErrorAlert } from '../../../components/ErrorAlert';
import { formatDateTime } from '../../../components/format';
import { useMe } from '../../auth/useAuth';
import { useProjectConnections } from '../../projects/useProjects';
import { RunStatusBadge } from '../RunStatusBadge';
import { type RunDetail, useLaunchRun } from '../useRuns';
import {
  type DumpPreview,
  PREVIEW_MAX_AGE_MS,
  rowsToDelete,
  TRUNCATE_WORD,
  useDumpPreview,
  usePreviewDumps,
} from './useDump';

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

function Warnings({ preview }: { preview: DumpPreview }) {
  const { t } = useTranslation();
  const missing = preview.tables.filter((table) => table.target_table === null);
  const required = preview.tables.filter((table) => table.missing_target_columns.length > 0);
  const notEmpty = preview.tables.filter((table) => (table.target_rows ?? 0) > 0);
  const items = [
    ...(missing.length
      ? [t('dump.warnings.missingTables', { tables: missing.map((x) => x.table).join(', ') })]
      : []),
    ...(required.length
      ? [t('dump.warnings.requiredColumns', { tables: required.map((x) => x.table).join(', ') })]
      : []),
    ...(!preview.truncate_target && notEmpty.length
      ? [t('dump.warnings.append', { tables: notEmpty.map((x) => x.table).join(', ') })]
      : []),
    ...(preview.cycles.length ? [t('dump.warnings.cycles', { count: preview.cycles.length })] : []),
    ...(preview.constraints_managed
      ? []
      : [t('dump.warnings.noConstraints', { engine: preview.target_engine })]),
  ];
  if (items.length === 0) return null;
  return (
    <Alert color="yellow" title={t('dump.warnings.title')}>
      <List size="sm">
        {items.map((item) => (
          <List.Item key={item}>{item}</List.Item>
        ))}
      </List>
    </Alert>
  );
}

function ConfirmDump({
  alias,
  truncate,
  deleting,
  opened,
  pending,
  error,
  onClose,
  onConfirm,
}: {
  alias: string;
  truncate: boolean;
  deleting: number;
  opened: boolean;
  pending: boolean;
  error: unknown;
  onClose: () => void;
  onConfirm: (confirmTruncate: string | null) => void;
}) {
  const { t } = useTranslation();
  const [understood, setUnderstood] = useState(false);
  const [typed, setTyped] = useState('');
  const [word, setWord] = useState('');
  const ready = understood && typed === alias && (!truncate || word === TRUNCATE_WORD);
  return (
    <Modal opened={opened} onClose={onClose} title={t('dump.apply.confirmTitle')}>
      <Stack>
        {error !== null && <ErrorAlert error={error} />}
        <Alert color="red" title={t('dump.apply.cancelTitle')}>
          {t('dump.apply.cancel', { alias })}
        </Alert>
        {truncate && (
          <Alert color="red" title={t('dump.apply.truncateTitle')}>
            {t('dump.apply.truncate', { count: deleting })}
          </Alert>
        )}
        <Checkbox
          label={t('dump.apply.understand')}
          checked={understood}
          onChange={(event) => setUnderstood(event.currentTarget.checked)}
        />
        <TextInput
          label={t('dump.apply.typeAlias', { alias })}
          value={typed}
          onChange={(event) => setTyped(event.currentTarget.value)}
          autoComplete="off"
        />
        {truncate && (
          <TextInput
            label={t('dump.apply.typeWord', { word: TRUNCATE_WORD })}
            value={word}
            onChange={(event) => setWord(event.currentTarget.value)}
            autoComplete="off"
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
            onClick={() => onConfirm(truncate ? word : null)}
          >
            {t('dump.apply.submit')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

/** Lanzar el volcado de una vista previa (ADR-009): permiso `can_write_data` + owner, destino no `read_only`. */
function DumpApplyPanel({ run, preview }: { run: RunDetail; preview: DumpPreview }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data: me } = useMe();
  const connections = useProjectConnections(run.project_id);
  const dumps = usePreviewDumps(run.project_id, run.id);
  const launch = useLaunchRun(run.project_id);
  const [confirming, setConfirming] = useState(false);

  const alias = String(run.params['target_connection']);
  const target = (connections.data ?? []).find((c) => c.alias === alias);
  const allowed = Boolean(me?.can_write_data) && run.my_role === 'owner';
  const finished = run.finished_at ? new Date(run.finished_at).getTime() : 0;
  // Referencia de «ahora»: la última consulta del historial (la API comprueba la hora real).
  const stale = dumps.dataUpdatedAt - finished > PREVIEW_MAX_AGE_MS;
  const reason = !allowed
    ? me?.can_write_data
      ? t('dump.apply.ownerOnly')
      : t('dump.apply.noPermission')
    : target?.read_only
      ? t('dump.apply.readOnly', { alias })
      : stale
        ? t('dump.apply.stale')
        : null;

  return (
    <Stack>
      <Title order={4}>{t('dump.apply.title')}</Title>
      {reason ? (
        <Text size="sm" c="dimmed">
          {reason}
        </Text>
      ) : (
        <Group>
          <Button color="red" onClick={() => setConfirming(true)}>
            {t(preview.truncate_target ? 'dump.apply.openTruncate' : 'dump.apply.open', { alias })}
          </Button>
          <ConfirmDump
            alias={alias}
            truncate={preview.truncate_target}
            deleting={rowsToDelete(preview)}
            opened={confirming}
            pending={launch.isPending}
            error={confirming && launch.isError ? launch.error : null}
            onClose={() => {
              setConfirming(false);
              launch.reset();
            }}
            onConfirm={(confirmTruncate) =>
              launch.mutate(
                {
                  operation: 'dump_apply',
                  params: {
                    preview_run: run.id,
                    confirm: alias,
                    ...(confirmTruncate ? { confirm_truncate: confirmTruncate } : {}),
                  },
                },
                { onSuccess: (created) => void navigate(`/runs/${created.id}`) },
              )
            }
          />
        </Group>
      )}
      {(dumps.data ?? []).length > 0 && (
        <Table striped withTableBorder aria-label={t('dump.apply.history')}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('runs.createdAt')}</Table.Th>
              <Table.Th>{t('runs.statusLabel')}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {(dumps.data ?? []).map((d) => (
              <Table.Tr key={d.id}>
                <Table.Td>
                  <Anchor component={Link} to={`/runs/${d.id}`}>
                    {formatDateTime(d.created_at)}
                  </Anchor>
                </Table.Td>
                <Table.Td>
                  <RunStatusBadge status={d.status} />
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}

/** Vista previa (modo seco) de un volcado y panel para lanzarlo (Fase 8). */
export function DumpPreviewViewer({ run }: { run: RunDetail }) {
  const { t } = useTranslation();
  const preview = useDumpPreview(run.id);
  const data = preview.data;
  return (
    <Card withBorder>
      <Stack>
        <Title order={3}>{t('dump.preview.title')}</Title>
        {preview.isPending && <Loader size="sm" aria-label={t('common.loading')} />}
        {preview.isError && <ErrorAlert error={preview.error} />}
        {data && (
          <>
            <Text size="sm">
              {t('dump.preview.route', {
                source: `${String(run.params['source_connection'])} (${data.source_engine})`,
                target: `${String(run.params['target_connection'])} (${data.target_engine})`,
              })}
              {data.truncate_target && (
                <Badge ml="xs" color="red" variant="light">
                  {t('dump.preview.truncates')}
                </Badge>
              )}
            </Text>
            <SimpleGrid cols={{ base: 2, sm: 4 }}>
              <Stat label={t('dump.preview.tables')} value={data.tables.length} />
              <Stat
                label={t('dump.preview.sourceRows')}
                value={data.tables.reduce((sum, x) => sum + x.source_rows, 0)}
              />
              <Stat
                label={t('dump.preview.missing')}
                value={data.tables.filter((x) => !x.target_table).length}
              />
              <Stat label={t('dump.preview.cycles')} value={data.cycles.length} />
            </SimpleGrid>
            <Warnings preview={data} />
            <Table striped withTableBorder aria-label={t('dump.preview.order')}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>#</Table.Th>
                  <Table.Th>{t('dump.preview.table')}</Table.Th>
                  <Table.Th>{t('dump.preview.sourceRows')}</Table.Th>
                  <Table.Th>{t('dump.preview.targetRows')}</Table.Th>
                  <Table.Th>{t('dump.preview.notes')}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {data.tables.map((table) => (
                  <Table.Tr key={table.table}>
                    <Table.Td>{table.position + 1}</Table.Td>
                    <Table.Td>
                      {table.table}
                      {table.in_cycle && (
                        <Badge ml="xs" variant="light" color="grape">
                          {t('dump.preview.inCycle')}
                        </Badge>
                      )}
                    </Table.Td>
                    <Table.Td>{table.source_rows}</Table.Td>
                    <Table.Td>
                      {table.target_table === null ? t('dump.preview.noTarget') : table.target_rows}
                    </Table.Td>
                    <Table.Td>
                      {[
                        table.skipped_columns.length
                          ? t('dump.preview.skipped', { columns: table.skipped_columns.join(', ') })
                          : '',
                        table.missing_target_columns.length
                          ? t('dump.preview.required', { columns: table.missing_target_columns.join(', ') })
                          : '',
                        table.outside_references.length
                          ? t('dump.preview.outside', { tables: table.outside_references.join(', ') })
                          : '',
                      ]
                        .filter(Boolean)
                        .join(' · ')}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
            <DumpApplyPanel run={run} preview={data} />
          </>
        )}
      </Stack>
    </Card>
  );
}
