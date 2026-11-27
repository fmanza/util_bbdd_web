import {
  type Icon,
  IconArchive,
  IconDatabase,
  IconDeviceDesktop,
  IconFolders,
  IconHistory,
  IconHome,
  IconListDetails,
  IconListSearch,
  IconPlugConnected,
  IconServer,
  IconSql,
  IconTemplate,
  IconUserShield,
  IconUsers,
  IconWorldCheck,
} from '@tabler/icons-react';

import type { Permission } from '../features/auth/useAuth';

/** Entrada del menú lateral: `label` es la clave i18n (de `core.json`, el menú está en el bundle inicial). */
export interface NavItem {
  to: string;
  label: string;
  icon: Icon;
  /** Solo activa con la ruta exacta (Inicio). */
  end?: boolean;
  /** Permiso del rol que exige (las de administración; ADR-014). */
  permission?: Permission;
}

export interface NavSection {
  /** Clave i18n del título de la sección; `null` para las entradas sueltas del principio. */
  title: string | null;
  items: readonly NavItem[];
}

/** Menú de todos los usuarios, agrupado por para qué sirve cada sección. */
export const MAIN_NAV: readonly NavSection[] = [
  { title: null, items: [{ to: '/', label: 'nav.home', icon: IconHome, end: true }] },
  {
    title: 'nav.sections.work',
    items: [
      { to: '/projects', label: 'nav.projects', icon: IconFolders },
      { to: '/runs', label: 'nav.runs', icon: IconHistory },
    ],
  },
  {
    title: 'nav.sections.data',
    items: [
      { to: '/connections', label: 'nav.connections', icon: IconPlugConnected },
      { to: '/engines', label: 'nav.engines', icon: IconDatabase },
    ],
  },
  {
    title: 'nav.sections.account',
    items: [{ to: '/account/storage', label: 'nav.myStorage', icon: IconArchive }],
  },
];

/** Administración, en subgrupos dentro de una sección plegable; cada entrada se ve con su permiso (ADR-014). */
export const ADMIN_NAV: readonly NavSection[] = [
  {
    title: 'nav.adminSections.access',
    items: [
      { to: '/admin/users', label: 'nav.users', icon: IconUsers, permission: 'users.manage' },
      { to: '/admin/roles', label: 'nav.roles', icon: IconUserShield, permission: 'roles.manage' },
      {
        to: '/admin/sessions',
        label: 'nav.sessions',
        icon: IconDeviceDesktop,
        permission: 'sessions.manage',
      },
      {
        to: '/admin/allowlist',
        label: 'nav.allowlist',
        icon: IconWorldCheck,
        permission: 'allowlist.manage',
      },
      { to: '/admin/audit', label: 'nav.audit', icon: IconListSearch, permission: 'audit.read' },
    ],
  },
  {
    title: 'nav.adminSections.shared',
    items: [
      { to: '/admin/templates', label: 'nav.templates', icon: IconTemplate, permission: 'templates.manage' },
      { to: '/admin/queries', label: 'nav.queries', icon: IconSql, permission: 'queries.manage' },
    ],
  },
  {
    title: 'nav.adminSections.operation',
    items: [
      { to: '/admin/runs', label: 'nav.adminRuns', icon: IconListDetails, permission: 'runs.admin' },
      { to: '/admin/storage', label: 'nav.storage', icon: IconServer, permission: 'storage.manage' },
    ],
  },
];

/** Secciones de administración con solo las entradas que permite `allowed` (sin las que se quedan vacías). */
export function allowedAdminNav(allowed: (permission: Permission) => boolean): NavSection[] {
  return ADMIN_NAV.map((s) => ({
    ...s,
    items: s.items.filter((i) => !i.permission || allowed(i.permission)),
  })).filter((s) => s.items.length > 0);
}

/** La entrada corresponde a la página `pathname` (ella o una de sus subpáginas). */
export function isActive(item: NavItem, pathname: string): boolean {
  if (item.end) return pathname === item.to;
  return pathname === item.to || pathname.startsWith(`${item.to}/`);
}

/** Clave de la sección de administración en las secciones plegadas del menú. */
export const ADMIN_SECTION_KEY = 'nav.admin';

/**
 * Secciones plegadas al empezar: ninguna, salvo que la versión anterior guardara la administración plegada
 * (`ubw.nav.adminOpened`, sustituida por `ubw.nav.folded`).
 */
export function initialFoldedSections(): Record<string, boolean> {
  try {
    return window.localStorage.getItem('ubw.nav.adminOpened') === 'false'
      ? { [ADMIN_SECTION_KEY]: true }
      : {};
  } catch {
    return {};
  }
}

/** Permiso que exige una ruta de administración (`undefined` si no es una de ellas). */
export function adminPermission(pathname: string): Permission | undefined {
  const item = ADMIN_NAV.flatMap((s) => s.items).find(
    (i) => pathname === i.to || pathname.startsWith(`${i.to}/`),
  );
  return item?.permission;
}
