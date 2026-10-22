import {
  Accordion,
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Loader,
  NativeSelect,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { type ReactNode, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../../components/ErrorAlert';
import { DefinitionDiff } from './DefinitionDiff';
import { DiffEvolutionPanel } from './DiffEvolution';
import { type DiffStatus, type SchemaDiff, type TableDiff, useRunDiff } from './useDiff';

/** Objetos que se muestran de cada pestaña antes de «Mostrar más». */
const PAGE = 100;
const STATUS_COLORS: Record<DiffStatus, string> = { added: 'green', removed: 'red', modified: 'yellow' };
type StatusFilter = DiffStatus | 'all';

export function StatusBadge({ status }: { status: DiffStatus }) {
  const { t } = useTranslation();
  return (
    <Badge color={STATUS_COLORS[status]} variant="light">
      {t(`diff.status.${status}`)}
    </Badge>
  );
}

function Rows({ headers, rows }: { headers: string[]; rows: ReactNode[][] }) {
  if (rows.length === 0) return null;
  return (
    <Table striped withTableBorder>
      <Table.Thead>
        <Table.Tr>
          {headers.map((header) => (
            <Table.Th key={header}>{header}</Table.Th>
          ))}
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {rows.map((cells, index) => (
          <Table.Tr key={index}>
            {cells.map((cell, column) => (
              <Table.Td key={column}>{cell}</Table.Td>
            ))}
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

function TableDetail({ table }: { table: TableDiff }) {
  const { t } = useTranslation();
  const [source, target] = [t('diff.source'), t('diff.target')];
  if (table.status !== 'modified') {
    return <Text size="sm">{t(`diff.tableOnly.${table.status}`)}</Text>;
  }
  return (
    <Stack>
      <Rows
        headers={[t('diff.column'), t('diff.attribute'), source, target]}
        rows={(table.column_diffs ?? []).map((c) => [
          c.column_name,
          t(`diff.attributes.${c.attribute}`),
          c.source_value,
          c.target_value,
        ])}
      />
      <Rows
        headers={[t('diff.index'), t('diff.state'), source, target]}
        rows={(table.index_diffs ?? []).map((i) => [
          i.index_name,
          <StatusBadge key="s" status={i.status} />,
          `${i.source_columns}${i.source_unique ? ' (UNIQUE)' : ''}`,
          `${i.target_columns}${i.target_unique ? ' (UNIQUE)' : ''}`,
        ])}
      />
      <Rows
        headers={[t('diff.foreignKey'), t('diff.state'), source, target]}
        rows={(table.fk_diffs ?? []).map((fk) => [
          fk.fk_name,
          <StatusBadge key="s" status={fk.status} />,
          fk.source_columns &&
            `${fk.source_columns} → ${fk.source_referred_table}(${fk.source_referred_columns})`,
          fk.target_columns &&
            `${fk.target_columns} → ${fk.target_referred_table}(${fk.target_referred_columns})`,
        ])}
      />
      <Rows
        headers={[t('diff.comment'), source, target]}
        rows={(table.comment_diffs ?? []).map((c) => [
          c.column_name ?? t('diff.tableComment'),
          c.source_comment,
          c.target_comment,
        ])}
      />
    </Stack>
  );
}

interface Entry {
  name: string;
  status: DiffStatus;
  extra?: string | undefined;
  body: () => ReactNode;
}

function EntryList({ entries, filter, status }: { entries: Entry[]; filter: string; status: StatusFilter }) {
  const { t } = useTranslation();
  const [limit, setLimit] = useState(PAGE);
  const needle = filter.trim().toLowerCase();
  const visible = entries.filter(
    (e) => (status === 'all' || e.status === status) && (!needle || e.name.toLowerCase().includes(needle)),
  );
  if (visible.length === 0) return <Text c="dimmed">{t('diff.noMatches')}</Text>;
  return (
    <Stack>
      <Accordion multiple variant="separated">
        {visible.slice(0, limit).map((entry) => (
          <Accordion.Item
            key={`${entry.name}-${entry.extra ?? ''}`}
            value={`${entry.name}-${entry.extra ?? ''}`}
          >
            <Accordion.Control>
              <Group gap="sm">
                <Text fw={500}>{entry.name}</Text>
                {entry.extra && (
                  <Text size="sm" c="dimmed">
                    {entry.extra}
                  </Text>
                )}
                <StatusBadge status={entry.status} />
              </Group>
            </Accordion.Control>
            <Accordion.Panel>{entry.body()}</Accordion.Panel>
          </Accordion.Item>
        ))}
      </Accordion>
      {visible.length > limit && (
        <Button variant="default" onClick={() => setLimit(limit + PAGE)}>
          {t('diff.showMore', { count: visible.length - limit })}
        </Button>
      )}
    </Stack>
  );
}

function counts(diff: SchemaDiff) {
  const tables = diff.table_diffs ?? [];
  return (['added', 'removed', 'modified'] as const).map((status) => ({
    status,
    count: tables.filter((table) => table.status === status).length,
  }));
}

function Viewer({ diff, runId, projectId }: { diff: SchemaDiff; runId: string; projectId: number }) {
  const { t } = useTranslation();
  const [filter, setFilter] = useState('');
  const [status, setStatus] = useState<StatusFilter>('all');
  const tables: Entry[] = (diff.table_diffs ?? []).map((table) => ({
    name: table.table_name,
    status: table.status,
    extra:
      table.status === 'modified'
        ? t('diff.tableCounts', {
            columns: table.column_diffs?.length ?? 0,
            indexes: table.index_diffs?.length ?? 0,
            fks: table.fk_diffs?.length ?? 0,
          })
        : undefined,
    body: () => <TableDetail table={table} />,
  }));
  const views: Entry[] = (diff.view_diffs ?? []).map((view) => ({
    name: view.view_name,
    status: view.status,
    body: () => (
      <DefinitionDiff source={view.source_definition ?? ''} target={view.target_definition ?? ''} />
    ),
  }));
  const routines: Entry[] = (diff.routine_diffs ?? []).map((routine) => ({
    name: routine.routine_name,
    status: routine.status,
    extra: routine.routine_type,
    body: () => (
      <DefinitionDiff source={routine.source_definition ?? ''} target={routine.target_definition ?? ''} />
    ),
  }));

  return (
    <Stack>
      <Text size="sm">
        <strong>{t('diff.source')}:</strong> {diff.source_label} · <strong>{t('diff.target')}:</strong>{' '}
        {diff.target_label}
      </Text>
      {!diff.has_differences ? (
        <Alert color="green" title={t('diff.identicalTitle')}>
          {t('diff.identical')}
        </Alert>
      ) : (
        <>
          <SimpleGrid cols={{ base: 2, sm: 4 }}>
            {counts(diff).map(({ status: s, count }) => (
              <Card key={s} withBorder padding="sm">
                <Text size="xs" c="dimmed">
                  {t(`diff.tablesStatus.${s}`)}
                </Text>
                <Text fw={700} size="xl">
                  {count}
                </Text>
              </Card>
            ))}
            <Card withBorder padding="sm">
              <Text size="xs" c="dimmed">
                {t('diff.leaves')}
              </Text>
              <Text fw={700} size="xl">
                {diff.total_leaf_differences}
              </Text>
            </Card>
          </SimpleGrid>
          <Text size="sm" c="dimmed">
            {t('diff.semantics')}
          </Text>
          <Group grow>
            <TextInput
              label={t('diff.filter')}
              value={filter}
              onChange={(event) => setFilter(event.currentTarget.value)}
            />
            <NativeSelect
              label={t('diff.state')}
              value={status}
              onChange={(event) => setStatus(event.currentTarget.value as StatusFilter)}
              data={[
                { value: 'all', label: t('diff.allStatuses') },
                ...(['added', 'removed', 'modified'] as const).map((s) => ({
                  value: s,
                  label: t(`diff.status.${s}`),
                })),
              ]}
            />
          </Group>
          <Tabs defaultValue="tables" keepMounted={false}>
            <Tabs.List>
              <Tabs.Tab value="tables">{t('diff.tabs.tables', { count: tables.length })}</Tabs.Tab>
              <Tabs.Tab value="views">{t('diff.tabs.views', { count: views.length })}</Tabs.Tab>
              <Tabs.Tab value="routines">{t('diff.tabs.routines', { count: routines.length })}</Tabs.Tab>
            </Tabs.List>
            <Tabs.Panel value="tables" pt="sm">
              <EntryList entries={tables} filter={filter} status={status} />
            </Tabs.Panel>
            <Tabs.Panel value="views" pt="sm">
              <EntryList entries={views} filter={filter} status={status} />
            </Tabs.Panel>
            <Tabs.Panel value="routines" pt="sm">
              <EntryList entries={routines} filter={filter} status={status} />
            </Tabs.Panel>
          </Tabs>
        </>
      )}
      <DiffEvolutionPanel runId={runId} projectId={projectId} />
    </Stack>
  );
}

/** Visor del diff de una ejecución `compare` terminada (Fase 6). */
export function DiffViewer({ runId, projectId }: { runId: string; projectId: number }) {
  const { t } = useTranslation();
  const diff = useRunDiff(runId, true);
  return (
    <Card withBorder>
      <Stack>
        <Title order={3}>{t('diff.title')}</Title>
        {diff.isPending && <Loader size="sm" aria-label={t('common.loading')} />}
        {diff.isError && <ErrorAlert error={diff.error} />}
        {diff.data && <Viewer diff={diff.data} runId={runId} projectId={projectId} />}
      </Stack>
    </Card>
  );
}
