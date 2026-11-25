import { Badge, Button, Center, Group, Loader, Select, Stack, Title } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { DataTable } from '../../components/DataTable';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import type { Column } from '../../components/tableState';
import { useListState } from '../../components/useListState';
import { useMe } from '../auth/useAuth';
import { DeleteUserModal } from './DeleteUserModal';
import { grantable, roleLabel } from './roleLabel';
import { type User, type UserFilters, useRoles, useUnlockUser, useUsers } from './useAdmin';
import { UserFormModal } from './UserFormModal';

type Editing = { user: User | null } | null;

// Valor del «Todos» de los filtros (Mantine no admite `''` como opción).
const ALL = 'all';
const STATUSES = ['active', 'inactive', 'locked'] as const;

function isLocked(user: User): boolean {
  return user.is_active && user.locked_until !== null && new Date(user.locked_until) > new Date();
}

/** Es el único administrador activo: no se puede desactivar, quitarle el rol ni borrar. */
function isLastAdmin(user: User, activeAdmins: number): boolean {
  return user.role.builtin === 'admin' && user.is_active && activeAdmins <= 1;
}

function UserStatus({ user, lastAdmin }: { user: User; lastAdmin: boolean }) {
  const { t } = useTranslation();
  const status = !user.is_active ? (
    <Badge color="gray">{t('admin.users.inactive')}</Badge>
  ) : isLocked(user) ? (
    <Badge color="orange">{t('admin.users.locked')}</Badge>
  ) : (
    <Badge color="green">{t('admin.users.activeBadge')}</Badge>
  );
  return (
    <Group gap={4} wrap="nowrap">
      {status}
      {lastAdmin && (
        <Badge color="blue" variant="outline" title={t('admin.users.lastAdminHint')}>
          {t('admin.users.lastAdmin')}
        </Badge>
      )}
    </Group>
  );
}

export function UsersPage() {
  const { t } = useTranslation();
  const list = useListState();
  const [filters, setFilters] = useState<UserFilters>({ role: '', status: '' });
  const [editing, setEditing] = useState<Editing>(null);
  const [deleting, setDeleting] = useState<User | null>(null);
  const { data, isPending, isError, error } = useUsers(list.state, filters);
  const unlock = useUnlockUser();
  const roles = useRoles();
  const { data: me } = useMe();
  const activeAdmins = data?.active_admins ?? 0;
  // Solo se actúa sobre quien no tiene permisos que tú no tienes (ADR-014; el backend respondería 403).
  const manageable = (u: User) => grantable(me?.permissions ?? [], u.permissions);

  const setFilter = (next: Partial<UserFilters>) => {
    setFilters((f) => ({ ...f, ...next }));
    list.resetPage();
  };

  const columns: Column<User>[] = [
    { key: 'username', header: t('auth.username'), sortable: true, cell: (u) => u.username },
    {
      key: 'display_name',
      header: t('admin.users.displayName'),
      sortable: true,
      cell: (u) => u.display_name,
    },
    { key: 'role', header: t('admin.users.role'), sortable: true, cell: (u) => roleLabel(t, u.role) },
    {
      key: 'status',
      header: t('admin.users.status'),
      cell: (u) => <UserStatus user={u} lastAdmin={isLastAdmin(u, activeAdmins)} />,
    },
    { key: 'projects', header: t('admin.users.projects'), sortable: true, cell: (u) => u.project_count },
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
        <Group gap="xs" wrap="nowrap">
          {manageable(u) && (
            <Button
              size="xs"
              variant="light"
              onClick={() => setEditing({ user: u })}
              aria-label={t('admin.users.editLabel', { username: u.username })}
            >
              {t('common.edit')}
            </Button>
          )}
          {isLocked(u) && (
            <Button
              size="xs"
              variant="light"
              color="orange"
              loading={unlock.isPending && unlock.variables === u.id}
              onClick={() => unlock.mutate(u.id)}
              aria-label={t('admin.users.unlockLabel', { username: u.username })}
            >
              {t('admin.users.unlock')}
            </Button>
          )}
          {!isLastAdmin(u, activeAdmins) && u.id !== me?.id && manageable(u) && (
            <Button
              size="xs"
              variant="light"
              color="red"
              onClick={() => setDeleting(u)}
              aria-label={t('admin.users.deleteLabel', { username: u.username })}
            >
              {t('admin.users.delete')}
            </Button>
          )}
        </Group>
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
      {unlock.isError && <ErrorAlert error={unlock.error} />}
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
          minWidth={880}
          toolbar={
            <>
              <Select
                label={t('admin.users.filterRole')}
                data={[
                  { value: ALL, label: t('admin.users.all') },
                  ...(roles.data ?? []).map((r) => ({ value: String(r.id), label: roleLabel(t, r) })),
                ]}
                value={filters.role || ALL}
                onChange={(value) => setFilter({ role: value && value !== ALL ? value : '' })}
                allowDeselect={false}
                w={170}
              />
              <Select
                label={t('admin.users.filterStatus')}
                data={[
                  { value: ALL, label: t('admin.users.all') },
                  { value: 'active', label: t('admin.users.activeBadge') },
                  { value: 'inactive', label: t('admin.users.inactive') },
                  { value: 'locked', label: t('admin.users.locked') },
                ]}
                value={filters.status || ALL}
                onChange={(value) => setFilter({ status: STATUSES.find((s) => s === value) ?? '' })}
                allowDeselect={false}
                w={170}
              />
            </>
          }
          {...list.table}
        />
      )}
      {editing && (
        <UserFormModal
          key={editing.user?.id ?? 'new'}
          user={editing.user}
          lastAdmin={editing.user ? isLastAdmin(editing.user, activeAdmins) : false}
          opened
          onClose={() => setEditing(null)}
        />
      )}
      {deleting && <DeleteUserModal key={deleting.id} user={deleting} onClose={() => setDeleting(null)} />}
    </Stack>
  );
}
