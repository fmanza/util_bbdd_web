import {
  Badge,
  Button,
  Center,
  Checkbox,
  Group,
  Loader,
  Modal,
  Stack,
  Text,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core';
import { type FormEvent, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { DataTable } from '../../components/DataTable';
import { ErrorAlert } from '../../components/ErrorAlert';
import type { Column } from '../../components/tableState';
import { useMe } from '../auth/useAuth';
import { grantable, roleLabel } from './roleLabel';
import {
  type PermissionInfo,
  type RoleOut,
  useCreateRole,
  useDeleteRole,
  usePermissionCatalog,
  useRoles,
  useUpdateRole,
} from './useAdmin';

const GROUPS = ['admin', 'databases'] as const;

/** Alta y edición de un rol: nombre y permisos agrupados. Los que no tienes salen desactivados (ADR-014). */
function RoleFormModal({
  role,
  catalog,
  onClose,
}: {
  /** Rol a editar; `null` para crear uno. */
  role: RoleOut | null;
  catalog: PermissionInfo[];
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const { data: me } = useMe();
  const create = useCreateRole();
  const update = useUpdateRole();
  const mutation = role ? update : create;
  const builtin = role?.builtin != null;
  const [name, setName] = useState(role ? roleLabel(t, role) : '');
  const [permissions, setPermissions] = useState<string[]>(role?.permissions ?? []);
  const [submitted, setSubmitted] = useState(false);
  const mine = me?.permissions ?? [];
  const nameError = submitted && !builtin && !name.trim() ? t('auth.required') : undefined;

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitted(true);
    if (!builtin && !name.trim()) return;
    // Se envían en el orden del catálogo.
    const ordered = catalog.map((p) => p.name).filter((p) => permissions.includes(p));
    if (role) {
      update.mutate(
        { id: role.id, body: builtin ? {} : { name: name.trim(), permissions: ordered } },
        { onSuccess: onClose },
      );
    } else {
      create.mutate({ name: name.trim(), permissions: ordered }, { onSuccess: onClose });
    }
  };

  return (
    <Modal
      opened
      onClose={onClose}
      size="lg"
      title={role ? t('admin.roles.editTitle', { name: roleLabel(t, role) }) : t('admin.roles.createTitle')}
    >
      <form onSubmit={onSubmit} noValidate>
        <Stack>
          {mutation.isError && <ErrorAlert error={mutation.error} />}
          {builtin && <Text size="sm">{t('admin.roles.builtinHint')}</Text>}
          <TextInput
            label={t('admin.roles.name')}
            required
            disabled={builtin}
            maxLength={64}
            value={name}
            onChange={(event) => setName(event.currentTarget.value)}
            error={nameError}
            data-autofocus
          />
          {GROUPS.map((group) => (
            <Checkbox.Group
              key={group}
              label={t(`admin.roles.groups.${group}`)}
              value={permissions}
              onChange={setPermissions}
            >
              <Stack gap="xs" mt="xs">
                {catalog
                  .filter((p) => p.group === group)
                  .map((p) => (
                    <Checkbox
                      key={p.name}
                      value={p.name}
                      label={t(`admin.permissions.${p.name}.label`)}
                      description={
                        mine.includes(p.name)
                          ? t(`admin.permissions.${p.name}.hint`)
                          : `${t(`admin.permissions.${p.name}.hint`)} ${t('admin.roles.notYours')}`
                      }
                      disabled={builtin || !mine.includes(p.name)}
                    />
                  ))}
              </Stack>
            </Checkbox.Group>
          ))}
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            {!builtin && (
              <Button type="submit" loading={mutation.isPending}>
                {t('common.save')}
              </Button>
            )}
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}

export function RolesPage() {
  const { t } = useTranslation();
  const { data: me } = useMe();
  const roles = useRoles();
  const catalog = usePermissionCatalog();
  const remove = useDeleteRole();
  const [editing, setEditing] = useState<{ role: RoleOut | null } | null>(null);
  const [deleting, setDeleting] = useState<RoleOut | null>(null);
  const mine = me?.permissions ?? [];

  const closeDelete = () => {
    setDeleting(null);
    remove.reset();
  };

  const columns: Column<RoleOut>[] = [
    {
      key: 'name',
      header: t('admin.roles.name'),
      sortable: true,
      searchable: true,
      value: (r) => roleLabel(t, r),
      cell: (r) => (
        <Group gap={6} wrap="nowrap">
          <Text size="sm" fw={500}>
            {roleLabel(t, r)}
          </Text>
          {r.builtin && (
            <Badge size="xs" variant="outline" tt="none" style={{ flexShrink: 0 }}>
              {t('admin.roles.builtin')}
            </Badge>
          )}
        </Group>
      ),
    },
    {
      key: 'permissions',
      header: t('admin.roles.permissions'),
      cell: (r) =>
        r.permissions.length === 0 ? (
          <Text size="sm" c="dimmed">
            {t('admin.roles.noPermissions')}
          </Text>
        ) : (
          <Group gap={4}>
            {r.permissions.map((p) => (
              <Badge key={p} size="sm" variant="light" tt="none">
                {t(`admin.permissions.${p}.label`)}
              </Badge>
            ))}
          </Group>
        ),
    },
    {
      key: 'user_count',
      header: t('admin.roles.users'),
      sortable: true,
      value: (r) => r.user_count,
      cell: (r) => r.user_count,
    },
    {
      key: 'actions',
      header: t('common.actions'),
      hiddenHeader: true,
      cell: (r) => {
        const own = grantable(mine, r.permissions);
        return (
          <Group gap="xs" wrap="nowrap">
            <Button
              size="xs"
              variant="light"
              onClick={() => setEditing({ role: r })}
              aria-label={t('admin.roles.editLabel', { name: roleLabel(t, r) })}
            >
              {r.builtin ? t('admin.roles.view') : t('common.edit')}
            </Button>
            {!r.builtin && (
              <Tooltip
                label={r.user_count > 0 ? t('admin.roles.inUse') : t('admin.roles.notYoursRole')}
                disabled={r.user_count === 0 && own}
              >
                <Button
                  size="xs"
                  variant="light"
                  color="red"
                  disabled={r.user_count > 0 || !own}
                  onClick={() => setDeleting(r)}
                  aria-label={t('admin.roles.deleteLabel', { name: r.name })}
                >
                  {t('admin.roles.delete')}
                </Button>
              </Tooltip>
            )}
          </Group>
        );
      },
    },
  ];

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{t('admin.roles.title')}</Title>
        <Button onClick={() => setEditing({ role: null })} disabled={!catalog.data}>
          {t('admin.roles.new')}
        </Button>
      </Group>
      <Text c="dimmed">{t('admin.roles.intro')}</Text>
      {(roles.isPending || catalog.isPending) && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {roles.isError && <ErrorAlert error={roles.error} />}
      {catalog.isError && <ErrorAlert error={catalog.error} />}
      {roles.data && (
        <DataTable
          mode="client"
          label={t('admin.roles.title')}
          searchLabel={t('admin.roles.search')}
          empty={t('table.noMatches')}
          columns={columns}
          rowKey={(r) => r.id}
          rows={roles.data}
        />
      )}
      {editing && catalog.data && (
        <RoleFormModal
          key={editing.role?.id ?? 'new'}
          role={editing.role}
          catalog={catalog.data}
          onClose={() => setEditing(null)}
        />
      )}
      <Modal opened={deleting !== null} onClose={closeDelete} title={t('admin.roles.deleteTitle')}>
        {deleting && (
          <Stack>
            <Text>{t('admin.roles.deleteBody', { name: deleting.name })}</Text>
            {remove.isError && <ErrorAlert error={remove.error} />}
            <Group justify="flex-end">
              <Button variant="default" onClick={closeDelete}>
                {t('common.cancel')}
              </Button>
              <Button
                color="red"
                loading={remove.isPending}
                onClick={() => remove.mutate(deleting.id, { onSuccess: closeDelete })}
              >
                {t('admin.roles.delete')}
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </Stack>
  );
}
