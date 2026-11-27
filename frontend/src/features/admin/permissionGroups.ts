import type { Icon } from '@tabler/icons-react';

import { ADMIN_NAV } from '../../app/navigation';
import type { PermissionInfo } from './useAdmin';

/** Grupo de permisos del formulario de rol: `title` es la clave i18n de su título. */
export interface PermissionGroup {
  title: string;
  permissions: { info: PermissionInfo; icon: Icon | null }[];
}

/** Título de los permisos sin entrada de menú, según el `group` que da la API. */
const FALLBACK_TITLES: Record<PermissionInfo['group'], string> = {
  admin: 'admin.roles.groups.admin',
  databases: 'admin.roles.groups.databases',
};

/**
 * Agrupa el catálogo como el menú: cada permiso de administración en la sección de `ADMIN_NAV` de su entrada (en
 * el orden del menú) y el resto por su `group` de la API, para que ningún permiso nuevo se quede fuera.
 */
export function permissionGroups(catalog: readonly PermissionInfo[]): PermissionGroup[] {
  const byName = new Map(catalog.map((p) => [p.name, p]));
  const placed = new Set<string>();
  const groups: PermissionGroup[] = [];
  for (const section of ADMIN_NAV) {
    const permissions: PermissionGroup['permissions'] = [];
    for (const item of section.items) {
      const info = item.permission ? byName.get(item.permission) : undefined;
      if (info && !placed.has(info.name)) {
        placed.add(info.name);
        permissions.push({ info, icon: item.icon });
      }
    }
    if (permissions.length > 0 && section.title) groups.push({ title: section.title, permissions });
  }
  for (const group of ['admin', 'databases'] as const) {
    const permissions = catalog
      .filter((p) => p.group === group && !placed.has(p.name))
      .map((info) => ({ info, icon: null }));
    if (permissions.length > 0) groups.push({ title: FALLBACK_TITLES[group], permissions });
  }
  return groups;
}
