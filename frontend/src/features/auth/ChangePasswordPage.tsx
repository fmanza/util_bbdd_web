import { Alert, Button, PasswordInput, Stack, Text, Title } from '@mantine/core';
import { type FormEvent, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { PASSWORD_MIN_LENGTH, useChangePassword } from './useAuth';

export function ChangePasswordPage() {
  const { t } = useTranslation();
  const change = useChangePassword();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const invalid = {
    current: !current,
    next: next.length < PASSWORD_MIN_LENGTH,
    confirm: confirm !== next,
  };
  const errors = {
    current: submitted && invalid.current ? t('auth.required') : undefined,
    next: submitted && invalid.next ? t('auth.passwordTooShort', { min: PASSWORD_MIN_LENGTH }) : undefined,
    confirm: submitted && invalid.confirm ? t('auth.passwordMismatch') : undefined,
  };

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitted(true);
    if (Object.values(invalid).some(Boolean)) {
      return;
    }
    change.mutate(
      { current_password: current, new_password: next },
      {
        onSuccess: () => {
          setCurrent('');
          setNext('');
          setConfirm('');
          setSubmitted(false);
        },
      },
    );
  };

  return (
    <Stack maw={480}>
      <Title order={2}>{t('auth.changePassword')}</Title>
      <Text c="dimmed">{t('auth.changePasswordIntro')}</Text>
      {change.isSuccess && (
        <Alert color="green" role="status" title={t('auth.passwordChanged')}>
          {t('auth.passwordChangedBody')}
        </Alert>
      )}
      {change.isError && <ErrorAlert error={change.error} />}
      <form onSubmit={onSubmit} noValidate>
        <Stack>
          <PasswordInput
            label={t('auth.currentPassword')}
            autoComplete="current-password"
            required
            value={current}
            onChange={(event) => setCurrent(event.currentTarget.value)}
            error={errors.current}
          />
          <PasswordInput
            label={t('auth.newPassword')}
            description={t('auth.passwordHint', { min: PASSWORD_MIN_LENGTH })}
            autoComplete="new-password"
            required
            value={next}
            onChange={(event) => setNext(event.currentTarget.value)}
            error={errors.next}
          />
          <PasswordInput
            label={t('auth.confirmPassword')}
            autoComplete="new-password"
            required
            value={confirm}
            onChange={(event) => setConfirm(event.currentTarget.value)}
            error={errors.confirm}
          />
          <Button type="submit" loading={change.isPending} w="fit-content">
            {t('auth.changePassword')}
          </Button>
        </Stack>
      </form>
    </Stack>
  );
}
