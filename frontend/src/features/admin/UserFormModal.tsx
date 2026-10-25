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
import { PASSWORD_MIN_LENGTH } from '../auth/useAuth';
import { type Role, type User, type UserUpdate, useCreateUser, useUpdateUser } from './useAdmin';

const USERNAME_PATTERN = /^[A-Za-z0-9._-]{3,64}$/;

interface UserFormModalProps {
  /** Usuario a editar; `null` para crear uno nuevo. */
  user: User | null;
  opened: boolean;
  onClose: () => void;
}

/** Alta y edición de usuario. Se monta con `key` distinta por usuario para reiniciar el estado. */
export function UserFormModal({ user, opened, onClose }: UserFormModalProps) {
  const { t } = useTranslation();
  const create = useCreateUser();
  const update = useUpdateUser();
  const mutation = user ? update : create;
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState(user?.display_name ?? '');
  const [role, setRole] = useState<Role>(user?.role ?? 'user');
  const [isActive, setIsActive] = useState(user?.is_active ?? true);
  const [canRunSql, setCanRunSql] = useState(user?.can_run_sql ?? false);
  const [canApplyDdl, setCanApplyDdl] = useState(user?.can_apply_ddl ?? false);
  const [canWriteData, setCanWriteData] = useState(user?.can_write_data ?? false);
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

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitted(true);
    if (Object.values(invalid).some(Boolean)) {
      return;
    }
    if (user) {
      const body: UserUpdate = {};
      if (displayName.trim() !== user.display_name) body.display_name = displayName.trim();
      if (role !== user.role) body.role = role;
      if (isActive !== user.is_active) body.is_active = isActive;
      if (canRunSql !== user.can_run_sql) body.can_run_sql = canRunSql;
      if (canApplyDdl !== user.can_apply_ddl) body.can_apply_ddl = canApplyDdl;
      if (canWriteData !== user.can_write_data) body.can_write_data = canWriteData;
      const quota = globalQuota ? null : quotaMb;
      if (quota !== ownQuota) body.storage_quota_mb = quota;
      if (password) body.password = password;
      update.mutate({ id: user.id, body }, { onSuccess: onClose });
    } else {
      create.mutate({ username, display_name: displayName.trim(), password, role }, { onSuccess: onClose });
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
            data={[
              { value: 'user', label: t('roles.user') },
              { value: 'admin', label: t('roles.admin') },
            ]}
            value={role}
            onChange={(value) => setRole(value === 'admin' ? 'admin' : 'user')}
            allowDeselect={false}
          />
          {user && (
            <Switch
              label={t('admin.users.active')}
              description={t('admin.users.activeHint')}
              checked={isActive}
              onChange={(event) => setIsActive(event.currentTarget.checked)}
            />
          )}
          {user && (
            <Switch
              label={t('admin.users.canRunSql')}
              description={t('admin.users.canRunSqlHint')}
              checked={canRunSql}
              onChange={(event) => setCanRunSql(event.currentTarget.checked)}
            />
          )}
          {user && (
            <Switch
              label={t('admin.users.canApplyDdl')}
              description={t('admin.users.canApplyDdlHint')}
              checked={canApplyDdl}
              onChange={(event) => setCanApplyDdl(event.currentTarget.checked)}
            />
          )}
          {user && (
            <Switch
              label={t('admin.users.canWriteData')}
              description={t('admin.users.canWriteDataHint')}
              checked={canWriteData}
              onChange={(event) => setCanWriteData(event.currentTarget.checked)}
            />
          )}
          {user && (
            <Switch
              label={t('admin.users.globalQuota')}
              description={t('admin.users.globalQuotaHint')}
              checked={globalQuota}
              onChange={(event) => setGlobalQuota(event.currentTarget.checked)}
            />
          )}
          {user && !globalQuota && (
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
