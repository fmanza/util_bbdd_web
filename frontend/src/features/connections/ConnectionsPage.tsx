import { Anchor, Badge, Button, Center, Group, Loader, Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { DataTable } from '../../components/DataTable';
import type { Column } from '../../components/tableState';
import { useListState } from '../../components/useListState';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { type ConnectionInfo, targetSummary, useConnections } from './useConnections';

export function LastTestBadge({ connection }: { connection: ConnectionInfo }) {
  const { t } = useTranslation();
  if (connection.last_test_ok === null) {
    return <Text c="dimmed">{t('connections.neverTested')}</Text>;
  }
  return (
    <Badge
      color={connection.last_test_ok ? 'green' : 'red'}
      variant="light"
      title={formatDateTime(connection.last_test_at)}
    >
      {connection.last_test_ok ? t('connections.testOk') : t('connections.testFailed')}
    </Badge>
  );
}

export function ConnectionsPage() {
  const { t } = useTranslation();
  const list = useListState();
  const { data, isPending, isError, error } = useConnections(list.state);
  const columns: Column<ConnectionInfo>[] = [
    {
      key: 'name',
      header: t('connections.name'),
      sortable: true,
      rowHeader: true,
      cell: (c) => (
        <Anchor component={Link} to={`/connections/${c.id}`}>
          {c.name}
        </Anchor>
      ),
    },
    { key: 'db_type', header: t('connections.engine'), sortable: true, cell: (c) => c.db_type },
    {
      key: 'target',
      header: t('connections.target'),
      cell: (c) => (
        <Text size="sm" ff="monospace">
          {targetSummary(c) || '—'}
        </Text>
      ),
    },
    {
      key: 'visibility',
      header: t('connections.access'),
      sortable: true,
      cell: (c) => (
        <Group gap={4}>
          {c.visibility === 'shared' && <Badge variant="light">{t('connections.visibility.shared')}</Badge>}
          {c.read_only && (
            <Badge variant="outline" color="gray">
              {t('connections.readOnly')}
            </Badge>
          )}
        </Group>
      ),
    },
    {
      key: 'last_test_at',
      header: t('connections.lastTest'),
      sortable: true,
      cell: (c) => <LastTestBadge connection={c} />,
    },
  ];

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{t('connections.title')}</Title>
        <Button component={Link} to="/connections/new">
          {t('connections.new')}
        </Button>
      </Group>
      {isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {isError && <ErrorAlert error={error} />}
      {data && (
        <DataTable
          mode="server"
          label={t('connections.title')}
          searchLabel={t('connections.search')}
          empty={t('connections.empty')}
          columns={columns}
          rowKey={(c) => c.id}
          rows={data.items}
          total={data.total}
          minWidth={820}
          {...list.table}
        />
      )}
    </Stack>
  );
}
