import {
  Button,
  Group,
  Modal,
  NumberInput,
  PasswordInput,
  Select,
  Stack,
  Switch,
  TextInput,
} from '@mantine/core';
import { type FormEvent, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { PASSWORD_MIN_LENGTH, useMe } from '../auth/useAuth';
import { grantable, roleLabel } from './roleLabel';
import { type User, type UserUpdate, useCreateUser, useRoles, useUpdateUser } from './useAdmin';

const USERNAME_PATTERN = /^[A-Za-z0-9._-]{3,64}$/;

interface UserFormModalProps {
  /** Usuario a editar; `null` para crear uno nuevo. */
  user: User | null;
  /** Es el único administrador activo: rol y estado no se pueden cambiar (el backend respondería 409). */
  lastAdmin?: boolean;
  opened: boolean;
  onClose: () => void;
}

/** Alta y edición de usuario. Se monta con `key` distinta por usuario para reiniciar el estado. */
export function UserFormModal({ user, lastAdmin = false, opened, onClose }: UserFormModalProps) {
  const { t } = useTranslation();
  const create = useCreateUser();
  const update = useUpdateUser();
  const { data: me } = useMe();
  const roles = useRoles(opened);
  const mutation = user ? update : create;
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState(user?.display_name ?? '');
  // Rol (ADR-014): sin elegir, el base «Usuario» al crear.
  const [roleId, setRoleId] = useState<number | null>(user?.role.id ?? null);
  const [isActive, setIsActive] = useState(user?.is_active ?? true);
  // Cuota propia en MB (ADR-012): `null` = la global; 0 = sin límite.
  const ownQuota = user?.storage_quota_mb ?? null;
  const [globalQuota, setGlobalQuota] = useState(ownQuota === null);
  const [quotaMb, setQuotaMb] = useState<number>(ownQuota ?? 1024);
  const [password, setPassword] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const invalid = {
    username: !user && !USERNAME_PATTERN.test(username),
    displayName: !displayName.trim(),
    password: (!user || password !== '') && password.length < PASSWORD_MIN_LENGTH,
  };
  const errors = {
    username: submitted && invalid.username ? t('admin.users.usernameRule') : undefined,
    displayName: submitted && invalid.displayName ? t('auth.required') : undefined,
    password:
      submitted && invalid.password ? t('auth.passwordTooShort', { min: PASSWORD_MIN_LENGTH }) : undefined,
  };

  // Nadie asigna un rol con permisos que no tiene, ni cambia el de quien tiene más, ni el suyo (ADR-014).
  const mine = me?.permissions ?? [];
  const defaultRole = roles.data?.find((r) => r.builtin === 'user');
  const roleOptions = (roles.data ?? []).map((r) => ({
    value: String(r.id),
    label: roleLabel(t, r),
    disabled: !grantable(mine, r.permissions),
  }));
  const roleLocked = lastAdmin
    ? t('admin.users.lastAdminHint')
    : user && user.id === me?.id
      ? t('admin.users.ownRoleHint')
      : user && !grantable(mine, user.permissions)
        ? t('admin.users.higherRoleHint')
        : null;

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitted(true);
    if (Object.values(invalid).some(Boolean)) {
      return;
    }
    if (user) {
      const body: UserUpdate = {};
      if (displayName.trim() !== user.display_name) body.display_name = displayName.trim();
      if (roleId !== null && roleId !== user.role.id) body.role_id = roleId;
      if (isActive !== user.is_active) body.is_active = isActive;
      const quota = globalQuota ? null : quotaMb;
      if (quota !== ownQuota) body.storage_quota_mb = quota;
      if (password) body.password = password;
      update.mutate({ id: user.id, body }, { onSuccess: onClose });
    } else {
      create.mutate(
        {
          username,
          display_name: displayName.trim(),
          password,
          role_id: roleId,
          is_active: isActive,
          storage_quota_mb: globalQuota ? null : quotaMb,
        },
        { onSuccess: onClose },
      );
    }
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={user ? t('admin.users.editTitle', { username: user.username }) : t('admin.users.createTitle')}
    >
      <form onSubmit={onSubmit} noValidate>
        <Stack>
          {mutation.isError && <ErrorAlert error={mutation.error} />}
          {!user && (
            <TextInput
              label={t('auth.username')}
              description={t('admin.users.usernameRule')}
              autoComplete="off"
              required
              value={username}
              onChange={(event) => setUsername(event.currentTarget.value)}
              error={errors.username}
              data-autofocus
            />
          )}
          <TextInput
            label={t('admin.users.displayName')}
            required
            value={displayName}
            onChange={(event) => setDisplayName(event.currentTarget.value)}
            error={errors.displayName}
          />
          <Select
            label={t('admin.users.role')}
            data={roleOptions}
            value={roleId === null ? (defaultRole ? String(defaultRole.id) : null) : String(roleId)}
            onChange={(value) => value && setRoleId(Number(value))}
            allowDeselect={false}
            disabled={roleLocked !== null}
            description={roleLocked ?? t('admin.users.roleHint')}
            error={roles.isError ? t('admin.users.rolesError') : undefined}
          />
          <Switch
            label={t('admin.users.active')}
            description={
              lastAdmin
                ? t('admin.users.lastAdminHint')
                : user
                  ? t('admin.users.activeHint')
                  : t('admin.users.activeOnCreateHint')
            }
            checked={isActive}
            disabled={lastAdmin}
            onChange={(event) => setIsActive(event.currentTarget.checked)}
          />
          <Switch
            label={t('admin.users.globalQuota')}
            description={t('admin.users.globalQuotaHint')}
            checked={globalQuota}
            onChange={(event) => setGlobalQuota(event.currentTarget.checked)}
          />
          {!globalQuota && (
            <NumberInput
              label={t('admin.users.quotaMb')}
              description={t('admin.users.quotaMbHint')}
              min={0}
              max={10_000_000}
              allowDecimal={false}
              allowNegative={false}
              value={quotaMb}
              onChange={(next) => typeof next === 'number' && setQuotaMb(next)}
            />
          )}
          <PasswordInput
            label={user ? t('admin.users.resetPassword') : t('auth.password')}
            description={
              user ? t('admin.users.resetPasswordHint') : t('auth.passwordHint', { min: PASSWORD_MIN_LENGTH })
            }
            autoComplete="new-password"
            required={!user}
            value={password}
            onChange={(event) => setPassword(event.currentTarget.value)}
            error={errors.password}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" loading={mutation.isPending}>
              {user ? t('common.save') : t('admin.users.create')}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
