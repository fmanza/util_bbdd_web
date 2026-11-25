import { AppShell, Burger, Group, NavLink, ScrollArea, Stack, Text, Title } from '@mantine/core';
import { useDisclosure, useLocalStorage } from '@mantine/hooks';
import { IconShieldLock } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { NavLink as RouterNavLink, Outlet, useLocation } from 'react-router';

import { UserMenu } from '../features/auth/UserMenu';
import { can, useMe } from '../features/auth/useAuth';
import { useColorSchemeSync } from '../features/auth/useColorSchemeSync';
import { useLanguageSync } from '../features/auth/useLanguageSync';
import { allowedAdminNav, MAIN_NAV, type NavItem, type NavSection } from './navigation';

function SectionTitle({ children }: { children: string }) {
  return (
    <Text size="xs" fw={700} c="dimmed" tt="uppercase" mt="sm" mb={2} px="sm" aria-hidden>
      {children}
    </Text>
  );
}

export function Layout() {
  const { t } = useTranslation();
  const { data: me } = useMe();
  useColorSchemeSync(me);
  useLanguageSync(me);
  const { pathname } = useLocation();
  // En móvil el menú se pliega tras la hamburguesa y se cierra al navegar.
  const [mobileOpened, { toggle: toggleMobile, close: closeMobile }] = useDisclosure(false);
  // Sección de administración plegable; abierta por defecto y siempre abierta en sus propias páginas.
  const [adminOpened, setAdminOpened] = useLocalStorage({
    key: 'ubw.nav.adminOpened',
    defaultValue: true,
    getInitialValueInEffect: false,
  });
  const inAdmin = pathname.startsWith('/admin/');
  const adminNav = allowedAdminNav((permission) => can(me, permission));

  const link = (item: NavItem) => (
    <NavLink
      key={item.to}
      component={RouterNavLink}
      to={item.to}
      end={item.end === true}
      label={t(item.label)}
      leftSection={<item.icon size={18} stroke={1.6} aria-hidden />}
      onClick={closeMobile}
    />
  );
  const section = (s: NavSection) => (
    <div
      key={s.title ?? 'top'}
      role={s.title ? 'group' : undefined}
      aria-label={s.title ? t(s.title) : undefined}
    >
      {s.title && <SectionTitle>{t(s.title)}</SectionTitle>}
      {s.items.map(link)}
    </div>
  );

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 248, breakpoint: 'sm', collapsed: { mobile: !mobileOpened } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Burger
              opened={mobileOpened}
              onClick={toggleMobile}
              hiddenFrom="sm"
              size="sm"
              aria-label={t(mobileOpened ? 'nav.closeMenu' : 'nav.openMenu')}
            />
            <Title order={1} size="h3">
              {t('app.title')}
            </Title>
          </Group>
          <UserMenu />
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="sm" aria-label={t('nav.label')}>
        <AppShell.Section grow component={ScrollArea}>
          <Stack gap={2}>
            {MAIN_NAV.map(section)}
            {adminNav.length > 0 && (
              <NavLink
                mt="md"
                label={t('nav.admin')}
                leftSection={<IconShieldLock size={18} stroke={1.6} aria-hidden />}
                opened={adminOpened || inAdmin}
                onChange={(opened) => {
                  if (!inAdmin) setAdminOpened(opened);
                }}
                {...(inAdmin ? { rightSection: null } : {})}
                childrenOffset={0}
                fw={600}
              >
                {adminNav.map(section)}
              </NavLink>
            )}
          </Stack>
        </AppShell.Section>
        <AppShell.Section>
          <Text size="xs" c="dimmed" pt="xs">
            v{__APP_VERSION__}
          </Text>
        </AppShell.Section>
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
