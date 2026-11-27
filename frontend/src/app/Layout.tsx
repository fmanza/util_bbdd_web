import {
  ActionIcon,
  AppShell,
  Burger,
  Divider,
  Group,
  NavLink,
  ScrollArea,
  Stack,
  Text,
  Title,
  Tooltip,
  UnstyledButton,
} from '@mantine/core';
import { useDisclosure, useLocalStorage } from '@mantine/hooks';
import {
  IconChevronDown,
  IconChevronRight,
  IconLayoutSidebarLeftCollapse,
  IconLayoutSidebarLeftExpand,
  IconShieldLock,
} from '@tabler/icons-react';
import { useId } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink as RouterNavLink, Outlet, useLocation } from 'react-router';

import { UserMenu } from '../features/auth/UserMenu';
import { can, useMe } from '../features/auth/useAuth';
import { useColorSchemeSync } from '../features/auth/useColorSchemeSync';
import { useLanguageSync } from '../features/auth/useLanguageSync';
import {
  ADMIN_SECTION_KEY,
  allowedAdminNav,
  initialFoldedSections,
  isActive,
  MAIN_NAV,
  type NavItem,
  type NavSection,
} from './navigation';

const NAV_WIDTH = 248;
/** Ancho del menú contraído: solo iconos. */
const RAIL_WIDTH = 64;
const NAVBAR_ID = 'app-navbar';

function SectionTitle({ children }: { children: string }) {
  return (
    <Text size="xs" fw={700} c="dimmed" tt="uppercase" mt="sm" mb={2} px="sm" aria-hidden>
      {children}
    </Text>
  );
}

/** Cabecera plegable de una sección del menú. */
function SectionToggle({
  title,
  opened,
  controls,
  onToggle,
}: {
  title: string;
  opened: boolean;
  controls: string;
  onToggle: () => void;
}) {
  const Chevron = opened ? IconChevronDown : IconChevronRight;
  return (
    <UnstyledButton
      onClick={onToggle}
      aria-expanded={opened}
      aria-controls={controls}
      w="100%"
      mt="sm"
      mb={2}
      px="sm"
    >
      <Group justify="space-between" wrap="nowrap" gap={4}>
        <Text size="xs" fw={700} c="dimmed" tt="uppercase">
          {title}
        </Text>
        <Chevron size={14} stroke={1.6} aria-hidden />
      </Group>
    </UnstyledButton>
  );
}

export function Layout() {
  const { t } = useTranslation();
  const { data: me } = useMe();
  useColorSchemeSync(me);
  useLanguageSync(me);
  const { pathname } = useLocation();
  const idPrefix = useId();
  // En móvil el menú se pliega tras la hamburguesa y se cierra al navegar.
  const [mobileOpened, { toggle: toggleMobile, close: closeMobile }] = useDisclosure(false);
  // En escritorio el menú entero se contrae a una barra de iconos.
  const [collapsed, setCollapsed] = useLocalStorage({
    key: 'ubw.nav.collapsed',
    defaultValue: false,
    getInitialValueInEffect: false,
  });
  // Secciones plegadas (por clave i18n del título); la que contiene la página actual está siempre abierta.
  const [folded, setFolded] = useLocalStorage<Record<string, boolean>>({
    key: 'ubw.nav.folded',
    defaultValue: initialFoldedSections(),
    getInitialValueInEffect: false,
  });
  // En móvil (menú abierto con la hamburguesa) siempre se ve entero.
  const rail = collapsed && !mobileOpened;
  const adminNav = allowedAdminNav((permission) => can(me, permission));
  const inAdmin = adminNav.some((s) => s.items.some((i) => isActive(i, pathname)));

  const link = (item: NavItem) => {
    const label = t(item.label);
    if (rail) {
      return (
        <Tooltip key={item.to} label={label} position="right" withArrow>
          <NavLink
            component={RouterNavLink}
            to={item.to}
            end={item.end === true}
            aria-label={label}
            leftSection={<item.icon size={20} stroke={1.6} aria-hidden />}
            onClick={closeMobile}
          />
        </Tooltip>
      );
    }
    return (
      <NavLink
        key={item.to}
        component={RouterNavLink}
        to={item.to}
        end={item.end === true}
        label={label}
        leftSection={<item.icon size={18} stroke={1.6} aria-hidden />}
        onClick={closeMobile}
      />
    );
  };

  const section = (s: NavSection) => {
    const key = s.title ?? 'top';
    if (rail) {
      return (
        <div key={key} role={s.title ? 'group' : undefined} aria-label={s.title ? t(s.title) : undefined}>
          {s.title && <Divider my={6} />}
          {s.items.map(link)}
        </div>
      );
    }
    if (!s.title) return <div key={key}>{s.items.map(link)}</div>;
    const title = t(s.title);
    const active = s.items.some((i) => isActive(i, pathname));
    const opened = active || folded[s.title] !== true;
    const listId = `${idPrefix}-${s.title}`;
    const sectionKey = s.title;
    return (
      <div key={key} role="group" aria-label={title}>
        {active ? (
          <SectionTitle>{title}</SectionTitle>
        ) : (
          <SectionToggle
            title={title}
            opened={opened}
            controls={listId}
            onToggle={() => setFolded((prev) => ({ ...prev, [sectionKey]: opened }))}
          />
        )}
        {opened && <div id={listId}>{s.items.map(link)}</div>}
      </div>
    );
  };

  const adminOpened = inAdmin || folded[ADMIN_SECTION_KEY] !== true;

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{
        width: rail ? RAIL_WIDTH : NAV_WIDTH,
        breakpoint: 'sm',
        collapsed: { mobile: !mobileOpened },
      }}
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
            <Tooltip label={t(collapsed ? 'nav.expandMenu' : 'nav.collapseMenu')}>
              <ActionIcon
                variant="subtle"
                color="gray"
                visibleFrom="sm"
                onClick={() => setCollapsed((c) => !c)}
                aria-label={t(collapsed ? 'nav.expandMenu' : 'nav.collapseMenu')}
                aria-expanded={!collapsed}
                aria-controls={NAVBAR_ID}
              >
                {collapsed ? (
                  <IconLayoutSidebarLeftExpand size={20} stroke={1.6} aria-hidden />
                ) : (
                  <IconLayoutSidebarLeftCollapse size={20} stroke={1.6} aria-hidden />
                )}
              </ActionIcon>
            </Tooltip>
            <Title order={1} size="h3">
              {t('app.title')}
            </Title>
          </Group>
          <UserMenu />
        </Group>
      </AppShell.Header>
      <AppShell.Navbar id={NAVBAR_ID} p={rail ? 'xs' : 'sm'} aria-label={t('nav.label')}>
        <AppShell.Section grow component={ScrollArea}>
          <Stack gap={2}>
            {MAIN_NAV.map(section)}
            {adminNav.length > 0 &&
              (rail ? (
                <div role="group" aria-label={t('nav.admin')}>
                  <Divider my={6} />
                  {adminNav.map(section)}
                </div>
              ) : (
                <NavLink
                  mt="md"
                  label={t('nav.admin')}
                  leftSection={<IconShieldLock size={18} stroke={1.6} aria-hidden />}
                  opened={adminOpened}
                  onChange={(opened) => {
                    if (!inAdmin) setFolded((prev) => ({ ...prev, [ADMIN_SECTION_KEY]: !opened }));
                  }}
                  {...(inAdmin ? { rightSection: null } : {})}
                  childrenOffset={0}
                  fw={600}
                >
                  {adminNav.map(section)}
                </NavLink>
              ))}
          </Stack>
        </AppShell.Section>
        <AppShell.Section>
          <Text size="xs" c="dimmed" pt="xs" {...(rail ? { ta: 'center' as const } : {})}>
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
