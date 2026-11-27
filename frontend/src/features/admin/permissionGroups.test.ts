import { describe, expect, it } from 'vitest';

import { PERMISSION_CATALOG } from '../../test/api';
import { permissionGroups } from './permissionGroups';
import type { PermissionInfo } from './useAdmin';

const CATALOG = PERMISSION_CATALOG as PermissionInfo[];

describe('permissionGroups', () => {
  it('reparte cada permiso del catálogo en un solo grupo, en el orden del menú', () => {
    const groups = permissionGroups(CATALOG);

    expect(groups.map((g) => g.title)).toEqual([
      'nav.adminSections.access',
      'nav.adminSections.shared',
      'nav.adminSections.operation',
      'admin.roles.groups.databases',
    ]);
    const names = groups.flatMap((g) => g.permissions.map((p) => p.info.name));
    expect([...names].sort()).toEqual(CATALOG.map((p) => p.name).sort());
    expect(groups[0]?.permissions.map((p) => p.info.name)).toEqual([
      'users.manage',
      'roles.manage',
      'sessions.manage',
      'allowlist.manage',
      'audit.read',
    ]);
  });

  it('un permiso sin entrada de menú cae en el grupo que da la API', () => {
    const groups = permissionGroups([{ name: 'sql.run', group: 'admin' }]);

    expect(groups).toEqual([
      {
        title: 'admin.roles.groups.admin',
        permissions: [{ info: { name: 'sql.run', group: 'admin' }, icon: null }],
      },
    ]);
  });
});
