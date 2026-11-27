import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';

import { ADMIN, session, stubApi, USER } from '../test/api';
import { renderRoute } from '../test/render';

const HEALTH = { 'GET /api/health': { body: { status: 'ok', checks: {} } } };

async function navigation() {
  return screen.findByRole('navigation', { name: 'Navegación principal' });
}

afterEach(() => {
  try {
    window.localStorage.clear();
  } catch {
    // sin almacenamiento: nada que limpiar
  }
});

describe('menú lateral', () => {
  it('agrupa las secciones por uso y no ofrece administración a un usuario', async () => {
    stubApi({ ...session(USER), ...HEALTH });
    renderRoute('/');
    const nav = await navigation();

    const work = within(nav).getByRole('group', { name: 'Trabajo' });
    expect(
      within(work)
        .getAllByRole('link')
        .map((a) => a.textContent),
    ).toEqual(['Proyectos', 'Ejecuciones']);
    const data = within(nav).getByRole('group', { name: 'Datos' });
    expect(
      within(data)
        .getAllByRole('link')
        .map((a) => a.textContent),
    ).toEqual(['Conexiones', 'Motores']);
    expect(within(nav).getByRole('link', { name: 'Mi espacio' })).toHaveAttribute('href', '/account/storage');
    expect(within(nav).getByRole('link', { name: 'Inicio' })).toHaveAttribute('aria-current', 'page');
    expect(within(nav).queryByText('Administración')).not.toBeInTheDocument();
  });

  it('la administración está agrupada y se puede plegar fuera de sus páginas', async () => {
    stubApi({ ...session(ADMIN), ...HEALTH });
    const user = userEvent.setup();
    renderRoute('/');
    const nav = await navigation();

    const access = within(nav).getByRole('group', { name: 'Acceso y seguridad' });
    expect(
      within(access)
        .getAllByRole('link')
        .map((a) => a.textContent),
    ).toEqual(['Usuarios', 'Roles', 'Sesiones', 'Destinos permitidos', 'Auditoría']);
    const operation = within(nav).getByRole('group', { name: 'Operación' });
    expect(within(operation).getByRole('link', { name: 'Todas las ejecuciones' })).toHaveAttribute(
      'href',
      '/admin/runs',
    );

    await user.click(within(nav).getByText('Administración'));
    expect(within(nav).queryByRole('link', { name: 'Usuarios' })).not.toBeInTheDocument();
  });

  it('en una página de administración la sección sigue abierta aunque se hubiera plegado', async () => {
    window.localStorage.setItem('ubw.nav.adminOpened', 'false');
    stubApi({ ...session(ADMIN), 'GET /api/v1/admin/users': { body: { items: [], total: 0 } } });
    renderRoute('/admin/users');
    const nav = await navigation();

    expect(within(nav).getByRole('link', { name: 'Usuarios' })).toHaveAttribute('aria-current', 'page');
  });

  it('las secciones se pliegan, se recuerdan y la de la página actual no se pliega', async () => {
    stubApi({ ...session(USER), ...HEALTH, 'GET /api/v1/projects': { body: { items: [], total: 0 } } });
    const user = userEvent.setup();
    renderRoute('/');
    const nav = await navigation();

    const toggle = within(nav).getByRole('button', { name: 'Datos' });
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    await user.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(within(nav).queryByRole('link', { name: 'Conexiones' })).not.toBeInTheDocument();
    expect(JSON.parse(window.localStorage.getItem('ubw.nav.folded') ?? '{}')).toEqual({
      'nav.sections.data': true,
    });

    // En una de sus páginas, «Trabajo» no ofrece plegarse.
    await user.click(within(nav).getByRole('link', { name: 'Proyectos' }));
    await waitFor(() =>
      expect(within(nav).getByRole('link', { name: 'Proyectos' })).toHaveAttribute('aria-current', 'page'),
    );
    expect(within(nav).queryByRole('button', { name: 'Trabajo' })).not.toBeInTheDocument();
  });

  it('respeta la administración plegada que guardó la versión anterior', async () => {
    window.localStorage.setItem('ubw.nav.adminOpened', 'false');
    stubApi({ ...session(ADMIN), ...HEALTH });
    renderRoute('/');
    const nav = await navigation();

    expect(within(nav).getByText('Administración')).toBeInTheDocument();
    expect(within(nav).queryByRole('link', { name: 'Usuarios' })).not.toBeInTheDocument();
  });

  it('el menú entero se contrae a iconos con nombre accesible y se recuerda', async () => {
    stubApi({ ...session(ADMIN), ...HEALTH });
    const user = userEvent.setup();
    renderRoute('/');
    const nav = await navigation();

    const collapse = screen.getByRole('button', { name: 'Contraer el menú' });
    expect(collapse).toHaveAttribute('aria-expanded', 'true');
    await user.click(collapse);

    expect(screen.getByRole('button', { name: 'Expandir el menú' })).toHaveAttribute(
      'aria-expanded',
      'false',
    );
    const home = within(nav).getByRole('link', { name: 'Inicio' });
    expect(home).toHaveAttribute('aria-current', 'page');
    expect(home).not.toHaveTextContent('Inicio');
    // Sin secciones plegables: todas las entradas, administración incluida.
    expect(within(nav).queryByRole('button', { name: 'Datos' })).not.toBeInTheDocument();
    expect(within(nav).getByRole('link', { name: 'Usuarios' })).toHaveAttribute('href', '/admin/users');
    expect(window.localStorage.getItem('ubw.nav.collapsed')).toBe('true');
  });

  it('la hamburguesa abre y cierra el menú en móvil', async () => {
    stubApi({ ...session(USER), ...HEALTH });
    const user = userEvent.setup();
    renderRoute('/');

    const burger = await screen.findByRole('button', { name: 'Abrir el menú' });
    await user.click(burger);
    expect(screen.getByRole('button', { name: 'Cerrar el menú' })).toBeInTheDocument();
    await user.click(within(await navigation()).getByRole('link', { name: 'Proyectos' }));
    expect(await screen.findByRole('button', { name: 'Abrir el menú' })).toBeInTheDocument();
  });
});
