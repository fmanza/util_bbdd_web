import {
  ActionIcon,
  Badge,
  Box,
  Code,
  CopyButton,
  Group,
  Loader,
  ScrollArea,
  Stack,
  Table,
  Tabs,
  Text,
  Title,
  Tooltip,
} from '@mantine/core';
import { type ReactNode, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { type ObjectKind, type TableDetail, useDdl, useTable } from './useExplorer';

export interface SelectedObject {
  kind: ObjectKind;
  name: string;
}

/**
 * Contenido de un apartado de la ficha: ocupa el alto que le deja la ficha y se desplaza dentro (vertical y
 * horizontal). Antes el DDL iba en un `ScrollArea` con solo `mah`, que no se desplaza: el DDL largo salía cortado.
 */
function Pane({ children, label }: { children: ReactNode; label: string }) {
  return (
    <Box style={{ flex: 1, minHeight: 0 }}>
      <ScrollArea h="100%" type="auto" offsetScrollbars aria-label={label}>
        {children}
      </ScrollArea>
    </Box>
  );
}

/** Pestañas de la ficha que llenan su alto: la lista arriba y el apartado activo con su propio scroll. */
const FILL: React.CSSProperties = { flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' };

function DdlView({
  connectionId,
  schema,
  object,
}: {
  connectionId: number;
  schema: string;
  object: SelectedObject;
}) {
  const { t } = useTranslation();
  const ddl = useDdl(connectionId, schema, object.kind, object.name, true);
  if (ddl.isPending) return <Loader size="sm" aria-label={t('common.loading')} />;
  if (ddl.isError) return <ErrorAlert error={ddl.error} />;
  if (!ddl.data.ddl) return <Text c="dimmed">{t('explorer.noDdl')}</Text>;
  const text = ddl.data.ddl;
  return (
    <Stack gap={4} style={FILL}>
      <Group justify="flex-end">
        <CopyButton value={text}>
          {({ copied, copy }) => (
            <Tooltip label={copied ? t('explorer.copied') : t('explorer.copyDdl')} withArrow>
              <ActionIcon variant="subtle" onClick={copy} aria-label={t('explorer.copyDdl')}>
                {copied ? '✓' : '⧉'}
              </ActionIcon>
            </Tooltip>
          )}
        </CopyButton>
      </Group>
      <Pane label="DDL">
        <Code block>{text}</Code>
      </Pane>
    </Stack>
  );
}

function Columns({ detail }: { detail: TableDetail }) {
  const { t } = useTranslation();
  const pk = new Set(detail.primary_key?.columns ?? []);
  return (
    <Table striped stickyHeader fz="sm" miw={640}>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>#</Table.Th>
          <Table.Th>{t('explorer.column')}</Table.Th>
          <Table.Th>{t('explorer.type')}</Table.Th>
          <Table.Th>{t('explorer.nullable')}</Table.Th>
          <Table.Th>{t('explorer.default')}</Table.Th>
          <Table.Th>{t('explorer.comment')}</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {detail.columns.map((column) => (
          <Table.Tr key={column.name}>
            <Table.Td>{column.ordinal}</Table.Td>
            <Table.Td>
              <Code>{column.name}</Code>{' '}
              {pk.has(column.name) && (
                <Badge size="xs" variant="light">
                  PK
                </Badge>
              )}
              {column.identity && (
                <Badge size="xs" variant="outline" ml={4}>
                  {t('explorer.identity')}
                </Badge>
              )}
            </Table.Td>
            <Table.Td ff="monospace">{column.data_type}</Table.Td>
            <Table.Td>{column.nullable ? t('common.yes') : t('common.no')}</Table.Td>
            <Table.Td ff="monospace">{column.default ?? '—'}</Table.Td>
            <Table.Td>{column.comment ?? '—'}</Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

function Keys({ detail }: { detail: TableDetail }) {
  const { t } = useTranslation();
  const rows = [
    ...(detail.primary_key
      ? [{ type: 'PK', name: detail.primary_key.name, def: detail.primary_key.columns.join(', ') }]
      : []),
    ...detail.uniques.map((u) => ({ type: 'UNIQUE', name: u.name, def: u.columns.join(', ') })),
    ...detail.checks.map((c) => ({ type: 'CHECK', name: c.name, def: c.expression })),
  ];
  if (rows.length === 0) return <Text c="dimmed">{t('explorer.noKeys')}</Text>;
  return (
    <Table striped stickyHeader fz="sm">
      <Table.Thead>
        <Table.Tr>
          <Table.Th>{t('explorer.keyType')}</Table.Th>
          <Table.Th>{t('explorer.name')}</Table.Th>
          <Table.Th>{t('explorer.definition')}</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {rows.map((row) => (
          <Table.Tr key={`${row.type}-${row.name}-${row.def}`}>
            <Table.Td>{row.type}</Table.Td>
            <Table.Td>{row.name || '—'}</Table.Td>
            <Table.Td ff="monospace">{row.def}</Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

function Indexes({ detail }: { detail: TableDetail }) {
  const { t } = useTranslation();
  if (detail.indexes.length === 0) return <Text c="dimmed">{t('explorer.noIndexes')}</Text>;
  return (
    <Table striped stickyHeader fz="sm">
      <Table.Thead>
        <Table.Tr>
          <Table.Th>{t('explorer.name')}</Table.Th>
          <Table.Th>{t('explorer.columns')}</Table.Th>
          <Table.Th>{t('explorer.unique')}</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {detail.indexes.map((index) => (
          <Table.Tr key={index.name}>
            <Table.Td>
              <Code>{index.name}</Code>
            </Table.Td>
            <Table.Td ff="monospace">{index.columns.join(', ')}</Table.Td>
            <Table.Td>{index.unique ? t('common.yes') : t('common.no')}</Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

function Relations({ detail, onOpen }: { detail: TableDetail; onOpen: (table: string) => void }) {
  const { t } = useTranslation();
  const row = (fk: TableDetail['foreign_keys'][number], outgoing: boolean) => (
    <Table.Tr key={`${outgoing ? 'out' : 'in'}-${fk.table}-${fk.name}-${fk.columns.join()}`}>
      <Table.Td>{outgoing ? t('explorer.references') : t('explorer.referencedBy')}</Table.Td>
      <Table.Td>
        <Text
          component="button"
          type="button"
          c="blue"
          td="underline"
          bg="none"
          bd="none"
          p={0}
          style={{ cursor: 'pointer' }}
          onClick={() => onOpen(outgoing ? fk.ref_table : fk.table)}
        >
          {outgoing ? fk.ref_table : fk.table}
        </Text>
      </Table.Td>
      <Table.Td ff="monospace">
        ({fk.columns.join(', ')}) → ({fk.ref_columns.join(', ')})
      </Table.Td>
      <Table.Td>{fk.on_delete}</Table.Td>
    </Table.Tr>
  );
  if (detail.foreign_keys.length + detail.referenced_by.length === 0) {
    return <Text c="dimmed">{t('explorer.noRelations')}</Text>;
  }
  return (
    <Table striped stickyHeader fz="sm">
      <Table.Thead>
        <Table.Tr>
          <Table.Th>{t('explorer.direction')}</Table.Th>
          <Table.Th>{t('explorer.table')}</Table.Th>
          <Table.Th>{t('explorer.columns')}</Table.Th>
          <Table.Th>ON DELETE</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {detail.foreign_keys.map((fk) => row(fk, true))}
        {detail.referenced_by.map((fk) => row(fk, false))}
      </Table.Tbody>
    </Table>
  );
}

export function ObjectDetail({
  connectionId,
  schema,
  object,
  onOpenTable,
}: {
  connectionId: number;
  schema: string;
  object: SelectedObject;
  onOpenTable: (table: string) => void;
}) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<string | null>('columns');
  const table = useTable(connectionId, schema, object.kind === 'table' ? object.name : null);

  return (
    <Stack style={{ ...FILL, height: '100%' }}>
      <Title order={3}>
        <Code fz="inherit">{object.name}</Code>{' '}
        <Badge variant="light">{t(`explorer.kinds.${object.kind}`)}</Badge>
      </Title>
      {object.kind !== 'table' ? (
        <DdlView connectionId={connectionId} schema={schema} object={object} />
      ) : table.isPending ? (
        <Loader aria-label={t('common.loading')} />
      ) : table.isError ? (
        <ErrorAlert error={table.error} />
      ) : (
        <Tabs value={tab} onChange={setTab} keepMounted={false} style={FILL}>
          <Tabs.List>
            <Tabs.Tab value="columns">
              {t('explorer.tabs.columns', { count: table.data.columns.length })}
            </Tabs.Tab>
            <Tabs.Tab value="keys">{t('explorer.tabs.keys')}</Tabs.Tab>
            <Tabs.Tab value="indexes">{t('explorer.tabs.indexes')}</Tabs.Tab>
            <Tabs.Tab value="relations">
              {t('explorer.tabs.relations', {
                count: table.data.foreign_keys.length + table.data.referenced_by.length,
              })}
            </Tabs.Tab>
            <Tabs.Tab value="ddl">DDL</Tabs.Tab>
          </Tabs.List>
          <Tabs.Panel value="columns" pt="sm" style={FILL}>
            <Pane label={t('explorer.tabs.columns', { count: table.data.columns.length })}>
              <Columns detail={table.data} />
            </Pane>
          </Tabs.Panel>
          <Tabs.Panel value="keys" pt="sm" style={FILL}>
            <Pane label={t('explorer.tabs.keys')}>
              <Keys detail={table.data} />
            </Pane>
          </Tabs.Panel>
          <Tabs.Panel value="indexes" pt="sm" style={FILL}>
            <Pane label={t('explorer.tabs.indexes')}>
              <Indexes detail={table.data} />
            </Pane>
          </Tabs.Panel>
          <Tabs.Panel value="relations" pt="sm" style={FILL}>
            <Pane
              label={t('explorer.tabs.relations', {
                count: table.data.foreign_keys.length + table.data.referenced_by.length,
              })}
            >
              <Relations detail={table.data} onOpen={onOpenTable} />
            </Pane>
          </Tabs.Panel>
          <Tabs.Panel value="ddl" pt="sm" style={FILL}>
            <DdlView connectionId={connectionId} schema={schema} object={object} />
          </Tabs.Panel>
        </Tabs>
      )}
    </Stack>
  );
}
