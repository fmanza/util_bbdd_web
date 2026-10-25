import { AppShell, Group, NavLink, Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { NavLink as RouterNavLink, Outlet } from 'react-router';

import { UserMenu } from '../features/auth/UserMenu';
import { useMe } from '../features/auth/useAuth';

// Secciones de la aplicación (las de fases futuras se añaden al implementarlas).
const SECTIONS: { key: string; to: string }[] = [
  { key: 'projects', to: '/projects' },
  { key: 'runs', to: '/runs' },
  { key: 'connections', to: '/connections' },
  { key: 'engines', to: '/engines' },
];

const ADMIN_SECTIONS = ['users', 'sessions', 'allowlist', 'queries', 'templates', 'audit'] as const;

export function Layout() {
  const { t } = useTranslation();
  const { data: me } = useMe();
  return (
    <AppShell header={{ height: 56 }} navbar={{ width: 240, breakpoint: 'sm' }} padding="md">
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Title order={1} size="h3">
            {t('app.title')}
          </Title>
          <UserMenu />
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="sm" aria-label={t('nav.label')}>
        <Stack gap={4}>
          <NavLink component={RouterNavLink} to="/" label={t('nav.home')} end />
          {SECTIONS.map((section) => (
            <NavLink
              key={section.key}
              component={RouterNavLink}
              to={section.to}
              label={t(`nav.${section.key}`)}
            />
          ))}
          {me?.role === 'admin' && (
            <>
              <Text size="xs" fw={700} c="dimmed" mt="md" px="sm">
                {t('nav.admin')}
              </Text>
              {ADMIN_SECTIONS.map((key) => (
                <NavLink key={key} component={RouterNavLink} to={`/admin/${key}`} label={t(`nav.${key}`)} />
              ))}
            </>
          )}
        </Stack>
        <Text size="xs" c="dimmed" mt="auto">
          v{__APP_VERSION__}
        </Text>
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
