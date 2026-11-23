import { useMantineColorScheme } from '@mantine/core';
import { act, renderHook, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it } from 'vitest';

import { Providers } from '../../app/Providers';
import { ADMIN, callsTo, session, stubApi, USER } from '../../test/api';
import { renderRoute } from '../../test/render';
import { type Me, safeNext } from './useAuth';
import { useColorSchemeSync } from './useColorSchemeSync';

function clearCookies() {
  for (const cookie of document.cookie.split('; ')) {
    const name = cookie.split('=')[0];
    if (name) document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
  }
}

afterEach(clearCookies);

describe('guardas de ruta', () => {
  it('sin sesión redirige al login', async () => {
    stubApi(session(null));

    renderRoute('/');

    expect(await screen.findByRole('button', { name: 'Iniciar sesión' })).toBeInTheDocument();
  });

  it('un usuario sin rol admin ve «sin permiso» en administración', async () => {
    stubApi(session(USER));

    renderRoute('/admin/users');

    expect(await screen.findByText('Sin permiso')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Usuarios' })).not.toBeInTheDocument();
  });

  it('el admin ve la sección de administración en la navegación', async () => {
    stubApi(session(ADMIN));

    renderRoute('/');

    expect(await screen.findByRole('link', { name: 'Usuarios' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Auditoría' })).toBeInTheDocument();
  });
});

describe('LoginPage', () => {
  it('inicia sesión con el token CSRF y vuelve a la ruta pedida', async () => {
    let loggedIn = false;
    const fetchMock = stubApi({
      ...session(null),
      'GET /api/v1/auth/me': () =>
        loggedIn ? { body: ADMIN } : { status: 401, body: { title: 'No autenticado', status: 401 } },
      'GET /api/v1/auth/csrf': { body: { csrf_token: 'tok-123' } },
      'POST /api/v1/auth/login': () => {
        loggedIn = true;
        return { body: ADMIN };
      },
      'GET /api/v1/users': { body: { items: [], total: 0 } },
    });
    const user = userEvent.setup();

    renderRoute('/login?next=%2Fadmin%2Fusers');
    await user.type(await screen.findByLabelText(/Usuario/), 'admin');
    await user.type(screen.getByLabelText(/Contraseña/), 'frase-de-paso-larga');
    await user.click(screen.getByRole('button', { name: 'Iniciar sesión' }));

    expect(await screen.findByRole('heading', { name: 'Usuarios' })).toBeInTheDocument();
    const [login] = callsTo(fetchMock, 'POST', '/api/v1/auth/login');
    expect(login?.headers.get('X-CSRF-Token')).toBe('tok-123');
    expect(await login?.json()).toEqual({ username: 'admin', password: 'frase-de-paso-larga' });
  });

  it('muestra el error genérico con credenciales incorrectas y vacía la contraseña', async () => {
    stubApi({
      ...session(null),
      'GET /api/v1/auth/csrf': { body: { csrf_token: 'tok' } },
      'POST /api/v1/auth/login': {
        status: 401,
        body: { title: 'Credenciales no válidas', status: 401, detail: 'Usuario o contraseña incorrectos.' },
      },
    });
    const user = userEvent.setup();

    renderRoute('/login');
    await user.type(await screen.findByLabelText(/Usuario/), 'ana');
    await user.type(screen.getByLabelText(/Contraseña/), 'mala');
    await user.click(screen.getByRole('button', { name: 'Iniciar sesión' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Credenciales no válidas');
    expect(screen.getByLabelText(/Contraseña/)).toHaveValue('');
  });

  it('valida campos obligatorios sin llamar a la API', async () => {
    const fetchMock = stubApi(session(null));
    const user = userEvent.setup();

    renderRoute('/login');
    await user.click(await screen.findByRole('button', { name: 'Iniciar sesión' }));

    expect(screen.getAllByText('Campo obligatorio')).toHaveLength(2);
    expect(callsTo(fetchMock, 'POST', '/api/v1/auth/login')).toHaveLength(0);
  });
});

describe('menú de usuario', () => {
  it('cierra sesión con la cabecera CSRF de la cookie', async () => {
    document.cookie = 'ubw_csrf=desde-cookie; path=/';
    let loggedIn = true;
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/auth/me': () =>
        loggedIn ? { body: ADMIN } : { status: 401, body: { title: 'No autenticado', status: 401 } },
      'POST /api/v1/auth/logout': () => {
        loggedIn = false;
        return { status: 204 };
      },
    });
    const user = userEvent.setup();

    renderRoute('/');
    // Con la suite entera en paralelo, el arranque de la SPA y la redirección tras el logout pasan de 1 s a veces.
    const slow = { timeout: 5000 };
    await user.click(await screen.findByRole('button', { name: /Menú de usuario de Admin/ }, slow));
    await user.click(await screen.findByRole('menuitem', { name: 'Cerrar sesión' }, slow));

    expect(await screen.findByRole('button', { name: 'Iniciar sesión' }, slow)).toBeInTheDocument();
    const [logout] = callsTo(fetchMock, 'POST', '/api/v1/auth/logout');
    expect(logout?.headers.get('X-CSRF-Token')).toBe('desde-cookie');
  }, 15_000);
});

describe('tema de la cuenta', () => {
  const slow = { timeout: 5000 };
  const scheme = () => document.documentElement.getAttribute('data-mantine-color-scheme');
  const radio = (name: string) => screen.getByRole('menuitemradio', { name, hidden: true });

  async function openMenu(user: ReturnType<typeof userEvent.setup>) {
    await user.click(await screen.findByRole('button', { name: /Menú de usuario de Ana/ }, slow));
    // En jsdom el desplegable de Mantine queda en `display: none` al acabar su transición (también sin estos
    // cambios) y solo es visible un instante: se espera a que esté montado (= abierto) y se consulta con `hidden`.
    return screen.findByRole('group', { name: 'Tema', hidden: true }, slow);
  }

  it('elegir «Oscuro» lo guarda con CSRF, cambia el tema y marca la opción', async () => {
    document.cookie = 'ubw_csrf=desde-cookie; path=/';
    const fetchMock = stubApi({
      ...session(USER),
      'PATCH /api/v1/auth/me/preferences': { body: { ...USER, color_scheme: 'dark' } },
    });
    const user = userEvent.setup();

    renderRoute('/');
    const group = await openMenu(user);
    expect(within(group).getAllByRole('menuitemradio', { hidden: true })).toHaveLength(3);
    expect(radio('Sistema')).toHaveAttribute('aria-checked', 'true');
    await user.click(radio('Oscuro'));

    await waitFor(() => expect(radio('Oscuro')).toHaveAttribute('aria-checked', 'true'));
    expect(radio('Sistema')).toHaveAttribute('aria-checked', 'false');
    expect(scheme()).toBe('dark');
    expect(localStorage.getItem('ubw-color-scheme')).toBe('dark');
    const [patch] = callsTo(fetchMock, 'PATCH', '/api/v1/auth/me/preferences');
    expect(patch?.headers.get('X-CSRF-Token')).toBe('desde-cookie');
    expect(await patch?.json()).toEqual({ color_scheme: 'dark' });
  }, 15_000);

  it('si el servidor falla, vuelve al tema anterior y lo avisa dentro del menú', async () => {
    stubApi({
      ...session(USER),
      'PATCH /api/v1/auth/me/preferences': { status: 500, body: { title: 'Error interno', status: 500 } },
    });
    const user = userEvent.setup();

    renderRoute('/');
    const group = await openMenu(user);
    expect(within(group).getAllByRole('menuitemradio', { hidden: true })).toHaveLength(3);
    await user.click(radio('Oscuro'));

    // El anuncio va fuera del `menu` (solo admite opciones, grupos y separadores); dentro, el aviso describe el grupo.
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('No se ha podido guardar el tema');
    expect(alert.closest('[role="menu"]')).toBeNull();
    const menu = screen.getByRole('menu', { hidden: true });
    expect(within(menu).queryByRole('alert', { hidden: true })).toBeNull();
    expect(group).toHaveAccessibleDescription(/No se ha podido guardar el tema/);
    expect(radio('Sistema')).toHaveAttribute('aria-checked', 'true');
    expect(radio('Oscuro')).toHaveAttribute('aria-checked', 'false');
    expect(scheme()).toBe('light');
    expect(localStorage.getItem('ubw-color-scheme')).toBe('auto');
  }, 15_000);

  function pendingPatch() {
    const pending: { release: () => void } = { release: () => undefined };
    const fetchMock = stubApi({
      ...session(USER),
      'PATCH /api/v1/auth/me/preferences': () =>
        new Promise((resolve) => {
          pending.release = () => resolve({ body: { ...USER, color_scheme: 'dark' } });
        }),
    });
    return { pending, fetchMock };
  }

  it('mientras se guarda, las opciones se marcan desactivadas sin perder el foco y no envían nada', async () => {
    const { pending, fetchMock } = pendingPatch();
    const user = userEvent.setup();

    renderRoute('/');
    const group = await openMenu(user);
    expect(within(group).getAllByRole('menuitemradio', { hidden: true })).toHaveLength(3);
    await user.click(radio('Oscuro'));

    await waitFor(() => expect(radio('Claro')).toHaveAttribute('aria-disabled', 'true'));
    // Sin `disabled` nativo: la opción con el foco sigue siendo enfocable (WCAG 2.4.3).
    expect(radio('Oscuro')).not.toBeDisabled();
    await user.click(radio('Claro'));
    expect(callsTo(fetchMock, 'PATCH', '/api/v1/auth/me/preferences')).toHaveLength(1);

    act(() => pending.release());
    await waitFor(() => expect(radio('Claro')).toHaveAttribute('aria-disabled', 'false'));
  }, 15_000);

  it('cerrar y reabrir el menú con el guardado en curso no reactiva las opciones', async () => {
    const { pending, fetchMock } = pendingPatch();
    const user = userEvent.setup();

    renderRoute('/');
    await openMenu(user);
    await user.click(radio('Oscuro'));
    await waitFor(() => expect(radio('Claro')).toHaveAttribute('aria-disabled', 'true'));

    const toggle = screen.getByRole('button', { name: /Menú de usuario de Ana/ });
    await user.click(toggle);
    await waitFor(() => expect(screen.queryByRole('group', { name: 'Tema', hidden: true })).toBeNull());
    await openMenu(user);

    expect(radio('Claro')).toHaveAttribute('aria-disabled', 'true');
    await user.click(radio('Claro'));
    expect(callsTo(fetchMock, 'PATCH', '/api/v1/auth/me/preferences')).toHaveLength(1);
    act(() => pending.release());
    await waitFor(() => expect(radio('Oscuro')).toHaveAttribute('aria-checked', 'true'));
  }, 15_000);

  it('la opción marcada se puede volver a elegir si otra pestaña cambió el tema', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      'PATCH /api/v1/auth/me/preferences': { body: USER },
    });
    const user = userEvent.setup();

    renderRoute('/');
    await openMenu(user);
    // Otra pestaña guarda «Oscuro»: Mantine lo aplica por el evento `storage`; la caché de `me` sigue en «Sistema».
    act(() => {
      localStorage.setItem('ubw-color-scheme', 'dark');
      window.dispatchEvent(
        new StorageEvent('storage', { key: 'ubw-color-scheme', newValue: 'dark', storageArea: localStorage }),
      );
    });
    await waitFor(() => expect(scheme()).toBe('dark'));
    expect(radio('Sistema')).toHaveAttribute('aria-checked', 'true');

    await user.click(radio('Sistema'));

    const [patch] = callsTo(fetchMock, 'PATCH', '/api/v1/auth/me/preferences');
    expect(await patch?.json()).toEqual({ color_scheme: 'auto' });
    await waitFor(() => expect(scheme()).toBe('light'));
    expect(localStorage.getItem('ubw-color-scheme')).toBe('auto');
  }, 15_000);

  it('al cargar, la cuenta manda sobre la copia local', async () => {
    localStorage.setItem('ubw-color-scheme', 'light');
    stubApi(session({ ...USER, color_scheme: 'dark' }));

    renderRoute('/');

    await waitFor(() => expect(scheme()).toBe('dark'), slow);
    expect(localStorage.getItem('ubw-color-scheme')).toBe('dark');
  }, 15_000);

  it('solo reacciona a cambios del tema de la cuenta y lo olvida al cerrar sesión', () => {
    const wrapper = ({ children }: { children: ReactNode }) => <Providers>{children}</Providers>;
    const ana: Me = { ...USER, color_scheme: 'dark' };
    const { result, rerender } = renderHook(
      ({ me }: { me: Me | null | undefined }) => {
        useColorSchemeSync(me);
        return useMantineColorScheme();
      },
      { wrapper, initialProps: { me: ana as Me | null | undefined } },
    );
    expect(result.current.colorScheme).toBe('dark');

    // Otra pestaña cambia el tema: la caché de `me` (sin cambios) no lo vuelve a imponer.
    act(() => result.current.setColorScheme('light'));
    rerender({ me: { ...ana } });
    expect(result.current.colorScheme).toBe('light');

    // Tras cerrar sesión, el siguiente usuario recibe su tema aunque coincida con el del anterior.
    rerender({ me: null });
    expect(result.current.colorScheme).toBe('light');
    rerender({ me: { ...USER, id: 3, username: 'berta', color_scheme: 'dark' } });
    expect(result.current.colorScheme).toBe('dark');
  });
});

describe('ChangePasswordPage', () => {
  it('valida y cambia la contraseña', async () => {
    const fetchMock = stubApi({ ...session(USER), 'POST /api/v1/auth/password': { status: 204 } });
    const user = userEvent.setup();

    renderRoute('/account/password');
    await user.type(await screen.findByLabelText(/Contraseña actual/), 'vieja');
    await user.type(screen.getByLabelText(/^Contraseña nueva/), 'corta');
    await user.click(screen.getByRole('button', { name: 'Cambiar contraseña' }));
    expect(screen.getByText('Debe tener al menos 12 caracteres')).toBeInTheDocument();
    expect(screen.getByText('Las contraseñas no coinciden')).toBeInTheDocument();

    await user.clear(screen.getByLabelText(/^Contraseña nueva/));
    await user.type(screen.getByLabelText(/^Contraseña nueva/), 'una-frase-larga');
    await user.type(screen.getByLabelText(/Repite/), 'una-frase-larga');
    await user.click(screen.getByRole('button', { name: 'Cambiar contraseña' }));

    expect(await screen.findByText('Contraseña cambiada')).toBeInTheDocument();
    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/auth/password')).toHaveLength(1));
  });
});

describe('safeNext', () => {
  it('solo admite rutas internas', () => {
    expect(safeNext('/admin/users')).toBe('/admin/users');
    expect(safeNext('//evil.example')).toBe('/');
    expect(safeNext('https://evil.example')).toBe('/');
    expect(safeNext('/login')).toBe('/');
    expect(safeNext(null)).toBe('/');
  });
});
