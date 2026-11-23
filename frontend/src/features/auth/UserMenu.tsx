import { Badge, Button, Menu, Text, VisuallyHidden } from '@mantine/core';
import { IconCheck, IconDeviceDesktop, IconMoon, IconSun } from '@tabler/icons-react';
import { useId } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';

import { type ColorScheme, useLogout, useMe, useUpdatePreferences } from './useAuth';

const THEME_OPTIONS: readonly { value: ColorScheme; icon: typeof IconSun }[] = [
  { value: 'light', icon: IconSun },
  { value: 'dark', icon: IconMoon },
  { value: 'auto', icon: IconDeviceDesktop },
];

/** `Menu.Item` fija `role="menuitem"` (Mantine 9) y no deja cambiarlo por props; React no vuelve a escribir un
 *  atributo cuya prop no cambia, así que basta con fijarlo al montar. `auth.test.tsx` vigila el rol. */
function asMenuItemRadio(node: HTMLElement | null) {
  node?.setAttribute('role', 'menuitemradio');
}

export function UserMenu() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data: me } = useMe();
  const logout = useLogout();
  const preferences = useUpdatePreferences();
  const themeLabelId = useId();
  const themeErrorId = useId();

  if (!me) {
    return null;
  }

  const onLogout = () => {
    logout.mutate(undefined, { onSettled: () => void navigate('/login', { replace: true }) });
  };

  return (
    <>
      <Menu
        position="bottom-end"
        withinPortal
        // Al cerrar se limpia el aviso de error, pero nunca con un guardado en curso: `reset()` desengancha la mutación
        // y volvería a activar las opciones mientras la petición sigue viva (carrera de dos guardados).
        onClose={() => {
          if (!preferences.isPending) preferences.reset();
        }}
      >
        <Menu.Target>
          <Button
            variant="subtle"
            rightSection={
              me.role === 'admin' ? (
                <Badge size="xs" variant="light">
                  {t('roles.admin')}
                </Badge>
              ) : undefined
            }
            aria-label={t('auth.userMenu', { name: me.display_name })}
          >
            {me.display_name}
          </Button>
        </Menu.Target>
        <Menu.Dropdown>
          <Menu.Label>{me.username}</Menu.Label>
          <Menu.Item component={Link} to="/account/storage">
            {t('auth.myStorage')}
          </Menu.Item>
          <Menu.Item component={Link} to="/account/password">
            {t('auth.changePassword')}
          </Menu.Item>
          <Menu.Divider />
          <Menu.Label id={themeLabelId}>{t('theme.label')}</Menu.Label>
          <div
            role="group"
            aria-labelledby={themeLabelId}
            aria-describedby={preferences.isError ? themeErrorId : undefined}
          >
            {THEME_OPTIONS.map(({ value, icon: Icon }) => {
              const checked = me.color_scheme === value;
              const busy = preferences.isPending;
              return (
                <Menu.Item
                  key={value}
                  ref={asMenuItemRadio}
                  aria-checked={checked}
                  closeMenuOnClick={false}
                  // Mientras se guarda: `aria-disabled` (no `disabled`), para que la opción con el foco lo conserve y el
                  // teclado siga dentro del menú (WCAG 2.4.3); el clic se ignora abajo.
                  aria-disabled={busy}
                  data-disabled={busy}
                  leftSection={<Icon size={16} stroke={1.6} aria-hidden />}
                  rightSection={checked ? <IconCheck size={16} stroke={1.8} aria-hidden /> : undefined}
                  // Sin guarda `checked`: en otra pestaña la marca (de `me`, en caché) puede no coincidir con el tema
                  // aplicado (sincronizado por `storage`); el PATCH es idempotente.
                  onClick={() => {
                    if (!busy) preferences.mutate(value);
                  }}
                >
                  {t(`theme.${value}`)}
                </Menu.Item>
              );
            })}
          </div>
          {/* Aviso visible sin rol (un `menu` solo admite opciones, grupos y separadores): describe el grupo y se
            anuncia desde la región `alert` de fuera del menú. */}
          {preferences.isError && (
            <Text id={themeErrorId} size="sm" c="red" px="sm" py={4} maw={240}>
              {t('theme.saveFailed')}
            </Text>
          )}
          <Menu.Divider />
          <Menu.Item onClick={onLogout} disabled={logout.isPending}>
            {t('auth.logout')}
          </Menu.Item>
        </Menu.Dropdown>
      </Menu>
      {preferences.isError && <VisuallyHidden role="alert">{t('theme.saveFailed')}</VisuallyHidden>}
    </>
  );
}
