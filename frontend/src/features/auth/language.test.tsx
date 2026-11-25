import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import i18n, { LANGUAGE_STORAGE_KEY } from '../../i18n';
import { callsTo, session, stubApi, USER } from '../../test/api';
import { renderRoute } from '../../test/render';

const slow = { timeout: 5000 };

async function openMenu(user: ReturnType<typeof userEvent.setup>, name: RegExp) {
  await user.click(await screen.findByRole('button', { name }, slow));
}

describe('idioma de la interfaz', () => {
  it('elegir «English» lo guarda en la cuenta y cambia la interfaz al momento', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      'PATCH /api/v1/auth/me/preferences': { body: { ...USER, language: 'en' } },
    });
    const user = userEvent.setup();

    renderRoute('/');
    await openMenu(user, /Menú de usuario de Ana/);
    const english = await screen.findByRole('menuitemradio', { name: 'English', hidden: true }, slow);
    expect(english).toHaveAttribute('lang', 'en');
    await user.click(english);

    await waitFor(() => expect(i18n.language).toBe('en'));
    expect(document.documentElement.lang).toBe('en');
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('en');
    expect(await callsTo(fetchMock, 'PATCH', '/api/v1/auth/me/preferences')[0]?.json()).toEqual({
      language: 'en',
    });
    expect(await screen.findByRole('link', { name: 'Projects' }, slow)).toBeInTheDocument();
  }, 15_000);

  it('el idioma de la cuenta gana a la copia local al llegar /me', async () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
    stubApi(session({ ...USER, language: 'en' }));

    renderRoute('/');

    expect(await screen.findByRole('link', { name: 'Projects' }, slow)).toBeInTheDocument();
    expect(document.documentElement.lang).toBe('en');
  }, 15_000);

  it('si el servidor falla, vuelve al idioma anterior', async () => {
    stubApi({
      ...session(USER),
      'PATCH /api/v1/auth/me/preferences': { status: 500, body: { title: 'Error interno', status: 500 } },
    });
    const user = userEvent.setup();

    renderRoute('/');
    await openMenu(user, /Menú de usuario de Ana/);
    await user.click(await screen.findByRole('menuitemradio', { name: 'English', hidden: true }, slow));

    await waitFor(() => expect(i18n.language).toBe('es'), slow);
    expect(await screen.findByRole('link', { name: 'Proyectos' }, slow)).toBeInTheDocument();
  }, 15_000);
});
