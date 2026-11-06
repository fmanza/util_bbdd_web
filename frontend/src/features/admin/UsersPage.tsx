import { Badge, Button, Center, Group, Loader, Stack, Title } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { DataTable } from '../../components/DataTable';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import type { Column } from '../../components/tableState';
import { useListState } from '../../components/useListState';
import { type User, useUsers } from './useAdmin';
import { UserFormModal } from './UserFormModal';

type Editing = { user: User | null } | null;

function UserStatus({ user }: { user: User }) {
  const { t } = useTranslation();
  if (!user.is_active) {
    return <Badge color="gray">{t('admin.users.inactive')}</Badge>;
  }
  if (user.locked_until && new Date(user.locked_until) > new Date()) {
    return <Badge color="orange">{t('admin.users.locked')}</Badge>;
  }
  return <Badge color="green">{t('admin.users.activeBadge')}</Badge>;
}

export function UsersPage() {
  const { t } = useTranslation();
  const list = useListState();
  const [editing, setEditing] = useState<Editing>(null);
  const { data, isPending, isError, error } = useUsers(list.state);
  const columns: Column<User>[] = [
    { key: 'username', header: t('auth.username'), sortable: true, cell: (u) => u.username },
    {
      key: 'display_name',
      header: t('admin.users.displayName'),
      sortable: true,
      cell: (u) => u.display_name,
    },
    { key: 'role', header: t('admin.users.role'), sortable: true, cell: (u) => t(`roles.${u.role}`) },
    { key: 'status', header: t('admin.users.status'), cell: (u) => <UserStatus user={u} /> },
    {
      key: 'created_at',
      header: t('admin.users.createdAt'),
      sortable: true,
      cell: (u) => formatDateTime(u.created_at),
    },
    {
      key: 'actions',
      header: t('common.actions'),
      hiddenHeader: true,
      cell: (u) => (
        <Button
          size="xs"
          variant="light"
          onClick={() => setEditing({ user: u })}
          aria-label={t('admin.users.editLabel', { username: u.username })}
        >
          {t('common.edit')}
        </Button>
      ),
    },
  ];

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{t('admin.users.title')}</Title>
        <Button onClick={() => setEditing({ user: null })}>{t('admin.users.new')}</Button>
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
          label={t('admin.users.title')}
          searchLabel={t('admin.users.search')}
          empty={t('admin.users.empty')}
          columns={columns}
          rowKey={(u) => u.id}
          rows={data.items}
          total={data.total}
          minWidth={720}
          {...list.table}
        />
      )}
      {editing && (
        <UserFormModal
          key={editing.user?.id ?? 'new'}
          user={editing.user}
          opened
          onClose={() => setEditing(null)}
        />
      )}
    </Stack>
  );
}
