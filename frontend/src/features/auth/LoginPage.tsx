import { Button, Center, Paper, PasswordInput, Stack, Text, TextInput, Title } from '@mantine/core';
import { type FormEvent, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, useNavigate, useSearchParams } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { safeNext, useLogin, useMe } from './useAuth';

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const next = safeNext(searchParams.get('next'));
  const { data: me } = useMe();
  const login = useLogin();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [submitted, setSubmitted] = useState(false);

  if (me) {
    return <Navigate to={next} replace />;
  }

  const usernameError = submitted && !username.trim() ? t('auth.required') : undefined;
  const passwordError = submitted && !password ? t('auth.required') : undefined;

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitted(true);
    if (!username.trim() || !password) {
      return;
    }
    login.mutate(
      { username: username.trim(), password },
      { onSuccess: () => void navigate(next, { replace: true }), onError: () => setPassword('') },
    );
  };

  return (
    <Center mih="100vh" p="md">
      <Paper withBorder shadow="sm" p="xl" w="100%" maw={400}>
        <form onSubmit={onSubmit} noValidate aria-labelledby="login-title">
          <Stack>
            <Title order={1} size="h3" id="login-title">
              {t('app.title')}
            </Title>
            <Text c="dimmed" size="sm">
              {t('auth.loginIntro')}
            </Text>
            {login.isError && <ErrorAlert error={login.error} />}
            <TextInput
              label={t('auth.username')}
              autoComplete="username"
              required
              value={username}
              onChange={(event) => setUsername(event.currentTarget.value)}
              error={usernameError}
              data-autofocus
            />
            <PasswordInput
              label={t('auth.password')}
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.currentTarget.value)}
              error={passwordError}
            />
            <Button type="submit" loading={login.isPending}>
              {t('auth.login')}
            </Button>
          </Stack>
        </form>
      </Paper>
    </Center>
  );
}
