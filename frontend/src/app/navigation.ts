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
  IconUsers,
  IconWorldCheck,
} from '@tabler/icons-react';

/** Entrada del menú lateral: `label` es la clave i18n (de `core.json`, el menú está en el bundle inicial). */
export interface NavItem {
  to: string;
  label: string;
  icon: Icon;
  /** Solo activa con la ruta exacta (Inicio). */
  end?: boolean;
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

/** Administración (solo rol admin), en subgrupos dentro de una sección plegable. */
export const ADMIN_NAV: readonly NavSection[] = [
  {
    title: 'nav.adminSections.access',
    items: [
      { to: '/admin/users', label: 'nav.users', icon: IconUsers },
      { to: '/admin/sessions', label: 'nav.sessions', icon: IconDeviceDesktop },
      { to: '/admin/allowlist', label: 'nav.allowlist', icon: IconWorldCheck },
      { to: '/admin/audit', label: 'nav.audit', icon: IconListSearch },
    ],
  },
  {
    title: 'nav.adminSections.shared',
    items: [
      { to: '/admin/templates', label: 'nav.templates', icon: IconTemplate },
      { to: '/admin/queries', label: 'nav.queries', icon: IconSql },
    ],
  },
  {
    title: 'nav.adminSections.operation',
    items: [
      { to: '/admin/runs', label: 'nav.adminRuns', icon: IconListDetails },
      { to: '/admin/storage', label: 'nav.storage', icon: IconServer },
    ],
  },
];
