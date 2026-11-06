import { Badge, Button, Center, Group, Loader, Modal, Stack, Text, Title } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { DataTable } from '../../components/DataTable';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import type { Column } from '../../components/tableState';
import { useListState } from '../../components/useListState';
import { type SessionInfo, useRevokeSession, useSessions } from './useAdmin';

export function SessionsPage() {
  const { t } = useTranslation();
  const list = useListState();
  const [revoking, setRevoking] = useState<SessionInfo | null>(null);
  const { data, isPending, isError, error } = useSessions(list.state);
  const revoke = useRevokeSession();

  const close = () => {
    setRevoking(null);
    revoke.reset();
  };
  const columns: Column<SessionInfo>[] = [
    {
      key: 'user',
      header: t('auth.username'),
      sortable: true,
      cell: (session) => (
        <Group gap="xs">
          {session.username}
          {session.current && (
            <Badge size="xs" variant="light">
              {t('admin.sessions.current')}
            </Badge>
          )}
        </Group>
      ),
    },
    { key: 'ip', header: t('admin.sessions.ip'), sortable: true, cell: (s) => s.ip ?? '—' },
    {
      key: 'user_agent',
      header: t('admin.sessions.userAgent'),
      cell: (s) => (
        <Text size="xs" lineClamp={1} title={s.user_agent ?? undefined}>
          {s.user_agent ?? '—'}
        </Text>
      ),
    },
    {
      key: 'created_at',
      header: t('admin.sessions.createdAt'),
      sortable: true,
      cell: (s) => formatDateTime(s.created_at),
    },
    {
      key: 'last_seen_at',
      header: t('admin.sessions.lastSeen'),
      sortable: true,
      cell: (s) => formatDateTime(s.last_seen_at),
    },
    {
      key: 'expires_at',
      header: t('admin.sessions.expiresAt'),
      sortable: true,
      cell: (s) => formatDateTime(s.expires_at),
    },
    {
      key: 'actions',
      header: t('common.actions'),
      hiddenHeader: true,
      cell: (session) => (
        <Button
          size="xs"
          color="red"
          variant="light"
          onClick={() => setRevoking(session)}
          aria-label={t('admin.sessions.revokeLabel', { username: session.username })}
        >
          {t('admin.sessions.revoke')}
        </Button>
      ),
    },
  ];

  return (
    <Stack>
      <Title order={2}>{t('admin.sessions.title')}</Title>
      <Text c="dimmed">{t('admin.sessions.intro')}</Text>
      {isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {isError && <ErrorAlert error={error} />}
      {data && (
        <DataTable
          mode="server"
          label={t('admin.sessions.title')}
          searchLabel={t('admin.sessions.search')}
          empty={t('admin.sessions.empty')}
          columns={columns}
          rowKey={(s) => s.id}
          rows={data.items}
          total={data.total}
          minWidth={820}
          {...list.table}
        />
      )}
      <Modal opened={revoking !== null} onClose={close} title={t('admin.sessions.confirmTitle')}>
        {revoking && (
          <Stack>
            <Text>
              {t('admin.sessions.confirmBody', { username: revoking.username, ip: revoking.ip ?? '—' })}
            </Text>
            {revoking.current && (
              <Text c="orange" fw={500}>
                {t('admin.sessions.confirmCurrent')}
              </Text>
            )}
            {revoke.isError && <ErrorAlert error={revoke.error} />}
            <Group justify="flex-end">
              <Button variant="default" onClick={close}>
                {t('common.cancel')}
              </Button>
              <Button
                color="red"
                loading={revoke.isPending}
                onClick={() => revoke.mutate(revoking, { onSuccess: close })}
              >
                {t('admin.sessions.revoke')}
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </Stack>
  );
}
