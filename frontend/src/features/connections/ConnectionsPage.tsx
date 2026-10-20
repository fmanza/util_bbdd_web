import {
  Anchor,
  Badge,
  Button,
  Center,
  Group,
  Loader,
  Pagination,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { type ConnectionInfo, PAGE_SIZE, targetSummary, useConnections } from './useConnections';

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
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const { data, isPending, isError, error } = useConnections(q.trim(), page);

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{t('connections.title')}</Title>
        <Button component={Link} to="/connections/new">
          {t('connections.new')}
        </Button>
      </Group>
      <TextInput
        label={t('connections.search')}
        value={q}
        onChange={(event) => {
          setQ(event.currentTarget.value);
          setPage(1);
        }}
        maw={320}
      />
      {isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {isError && <ErrorAlert error={error} />}
      {data && data.items.length === 0 && <Text c="dimmed">{t('connections.empty')}</Text>}
      {data && data.items.length > 0 && (
        <Table.ScrollContainer minWidth={820}>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('connections.name')}</Table.Th>
                <Table.Th>{t('connections.engine')}</Table.Th>
                <Table.Th>{t('connections.target')}</Table.Th>
                <Table.Th>{t('connections.access')}</Table.Th>
                <Table.Th>{t('connections.lastTest')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.items.map((connection) => (
                <Table.Tr key={connection.id}>
                  <Table.Th scope="row">
                    <Anchor component={Link} to={`/connections/${connection.id}`}>
                      {connection.name}
                    </Anchor>
                  </Table.Th>
                  <Table.Td>{connection.db_type}</Table.Td>
                  <Table.Td>
                    <Text size="sm" ff="monospace">
                      {targetSummary(connection) || '—'}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Group gap={4}>
                      {connection.visibility === 'shared' && (
                        <Badge variant="light">{t('connections.visibility.shared')}</Badge>
                      )}
                      {connection.read_only && (
                        <Badge variant="outline" color="gray">
                          {t('connections.readOnly')}
                        </Badge>
                      )}
                    </Group>
                  </Table.Td>
                  <Table.Td>
                    <LastTestBadge connection={connection} />
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {data && data.total > PAGE_SIZE && (
        <Pagination total={Math.ceil(data.total / PAGE_SIZE)} value={page} onChange={setPage} />
      )}
    </Stack>
  );
}
