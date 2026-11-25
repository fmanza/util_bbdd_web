import type { TFunction } from 'i18next';

/** Nombre visible de un rol: el de los roles base sale de las traducciones (`roles.admin`, `roles.user`). */
export function roleLabel(t: TFunction, role: { name: string; builtin: 'admin' | 'user' | null }): string {
  return role.builtin ? t(`roles.${role.builtin}`) : role.name;
}

/** `permissions` está contenido en `mine` (nadie asigna lo que no tiene, ADR-014). */
export function grantable(mine: readonly string[], permissions: readonly string[]): boolean {
  return permissions.every((p) => mine.includes(p));
}
