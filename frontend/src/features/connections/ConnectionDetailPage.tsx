import {
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Code,
  Group,
  Loader,
  Modal,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { LastTestBadge } from './ConnectionsPage';
import {
  type ConnectionTest,
  type Readiness,
  useConnection,
  useDeleteConnection,
  useReadiness,
  useTestConnection,
} from './useConnections';

const LEVEL_COLORS: Record<string, string> = {
  CRITICAL: 'red',
  WARNING: 'orange',
  INFO: 'blue',
  OK: 'green',
};

function TestResult({ result }: { result: ConnectionTest }) {
  const { t } = useTranslation();
  if (result.ok) {
    return (
      <Alert color="green" title={t('connections.testOkTitle')}>
        {t('connections.testOkBody', { version: result.server_version ?? '—', ms: result.duration_ms })}
      </Alert>
    );
  }
  return (
    <Alert color="red" title={t('connections.testFailedTitle')}>
      {result.error?.message}
    </Alert>
  );
}

function ReadinessReport({ report }: { report: Readiness }) {
  const { t } = useTranslation();
  if (report.error) {
    return (
      <Alert color="red" title={t('connections.readinessFailed')}>
        {report.error.message}
      </Alert>
    );
  }
  return (
    <Stack gap="xs">
      {!report.supported && <Text c="dimmed">{t('connections.readinessUnsupported')}</Text>}
      {report.supported && !report.dynamic && (
        <Alert color="yellow">{t('connections.readinessStatic', { detail: report.detail ?? '—' })}</Alert>
      )}
      {report.findings.length > 0 && (
        <Table.ScrollContainer minWidth={640}>
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('connections.level')}</Table.Th>
                <Table.Th>{t('connections.param')}</Table.Th>
                <Table.Th>{t('connections.current')}</Table.Th>
                <Table.Th>{t('connections.recommendation')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {report.findings.map((finding) => (
                <Table.Tr key={`${finding.level}-${finding.param}`}>
                  <Table.Td>
                    <Badge color={LEVEL_COLORS[finding.level] ?? 'gray'} variant="light">
                      {finding.level}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Code>{finding.param}</Code>
                  </Table.Td>
                  <Table.Td>{finding.current}</Table.Td>
                  <Table.Td>{finding.recommendation || '—'}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {report.checked_at && (
        <Text size="xs" c="dimmed">
          {t('connections.checkedAt', { date: formatDateTime(report.checked_at) })}
        </Text>
      )}
    </Stack>
  );
}

export function ConnectionDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const id = Number(useParams().connectionId);
  const { data: connection, isPending, isError, error } = useConnection(id);
  const test = useTestConnection(id);
  const [readinessRequested, setReadinessRequested] = useState(false);
  const readiness = useReadiness(id, readinessRequested);
  const remove = useDeleteConnection(id);
  const [confirmDelete, setConfirmDelete] = useState(false);

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

  const params = Object.entries(connection.params as Record<string, unknown>);

  return (
    <Stack maw={960}>
      <Group justify="space-between">
        <Group gap="xs">
          <Title order={2}>{connection.name}</Title>
          <Badge variant="light">{connection.db_type}</Badge>
          {connection.visibility === 'shared' && <Badge>{t('connections.visibility.shared')}</Badge>}
          {connection.read_only && (
            <Badge variant="outline" color="gray">
              {t('connections.readOnly')}
            </Badge>
          )}
        </Group>
        {connection.editable && (
          <Group gap="xs">
            <Button variant="default" component={Link} to={`/connections/${connection.id}/edit`}>
              {t('common.edit')}
            </Button>
            <Button color="red" variant="light" onClick={() => setConfirmDelete(true)}>
              {t('common.delete')}
            </Button>
          </Group>
        )}
      </Group>
      {connection.description && <Text>{connection.description}</Text>}
      <Card withBorder>
        <Table>
          <Table.Tbody>
            {params.map(([name, value]) => (
              <Table.Tr key={name}>
                <Table.Th w={220}>
                  <Code>{name}</Code>
                </Table.Th>
                <Table.Td>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</Table.Td>
              </Table.Tr>
            ))}
            <Table.Tr>
              <Table.Th>{t('connections.form.password')}</Table.Th>
              <Table.Td>
                {connection.has_password ? t('connections.passwordStored') : t('connections.noPassword')}
              </Table.Td>
            </Table.Tr>
            <Table.Tr>
              <Table.Th>{t('connections.owner')}</Table.Th>
              <Table.Td>{connection.owner_username}</Table.Td>
            </Table.Tr>
            <Table.Tr>
              <Table.Th>{t('connections.lastTest')}</Table.Th>
              <Table.Td>
                <LastTestBadge connection={connection} />
              </Table.Td>
            </Table.Tr>
          </Table.Tbody>
        </Table>
      </Card>
      <Group>
        <Button onClick={() => test.mutate()} loading={test.isPending}>
          {t('connections.test')}
        </Button>
        <Button
          variant="light"
          onClick={() => (readinessRequested ? void readiness.refetch() : setReadinessRequested(true))}
          loading={readiness.isFetching}
        >
          {t('connections.readiness')}
        </Button>
      </Group>
      <div aria-live="polite">
        {test.isError && <ErrorAlert error={test.error} />}
        {test.data && <TestResult result={test.data} />}
      </div>
      {readinessRequested && (
        <Stack gap="xs" aria-live="polite">
          <Title order={3}>{t('connections.readinessTitle')}</Title>
          {readiness.isError && <ErrorAlert error={readiness.error} />}
          {readiness.data && <ReadinessReport report={readiness.data} />}
        </Stack>
      )}
      <Modal
        opened={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        title={t('connections.deleteTitle')}
      >
        <Stack>
          <Text>{t('connections.deleteBody', { name: connection.name })}</Text>
          {remove.isError && <ErrorAlert error={remove.error} />}
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setConfirmDelete(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              color="red"
              loading={remove.isPending}
              onClick={() => remove.mutate(undefined, { onSuccess: () => void navigate('/connections') })}
            >
              {t('common.delete')}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
