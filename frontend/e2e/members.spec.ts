import { expect, type Page, test } from './fixtures';

// Miembros y roles de un proyecto (Fase 10). Requiere el admin E2E (UBW_E2E_ADMIN_USER / UBW_E2E_ADMIN_PASSWORD).
const ADMIN_USER = process.env.UBW_E2E_ADMIN_USER;
const ADMIN_PASSWORD = process.env.UBW_E2E_ADMIN_PASSWORD;

test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define UBW_E2E_ADMIN_USER y UBW_E2E_ADMIN_PASSWORD');

async function login(page: Page, username: string, password: string) {
  await page.goto('/login');
  await page.getByLabel('Usuario').fill(username);
  await page.getByLabel('Contraseña').fill(password);
  await page.getByRole('button', { name: 'Iniciar sesión' }).click();
  await expect(page.getByRole('button', { name: /Menú de usuario/ })).toBeVisible();
}

test('un lector ve el proyecto sin poder lanzar; como editor lanza pero no ve los ajustes', async ({
  page,
  browser,
}) => {
  test.setTimeout(120_000);
  const stamp = Date.now();
  const [username, project] = [`e2e-miembro-${stamp}`, `e2e-roles-${stamp}`];
  const password = 'frase-de-paso-miembro-1234';

  await login(page, ADMIN_USER ?? '', ADMIN_PASSWORD ?? '');
  await page.goto('/admin/users');
  await page.getByRole('button', { name: 'Nuevo usuario' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('textbox', { name: /^Usuario/ }).fill(username);
  await dialog.getByRole('textbox', { name: /Nombre visible/ }).fill('Miembro E2E');
  await dialog.getByLabel(/^Contraseña/).fill(password);
  await dialog.getByRole('button', { name: 'Crear usuario' }).click();
  await expect(dialog).toBeHidden();
  // La lista está paginada: se busca el usuario nuevo.
  await page.getByRole('textbox', { name: 'Buscar por usuario o nombre' }).fill(username);
  await expect(page.getByRole('cell', { name: username, exact: true })).toBeVisible();

  await page.goto('/projects');
  await page.getByRole('button', { name: 'Nuevo proyecto' }).click();
  await page
    .getByRole('dialog')
    .getByRole('textbox', { name: /^Nombre/ })
    .fill(project);
  await page.getByRole('dialog').getByRole('button', { name: 'Crear proyecto' }).click();
  await expect(page.getByRole('heading', { name: project })).toBeVisible();
  const projectUrl = page.url();
  await page.getByRole('tab', { name: 'Miembros' }).click();
  const members = page.getByRole('tabpanel', { name: 'Miembros' });
  await members.getByRole('textbox', { name: 'Usuario', exact: true }).fill(username);
  await members.getByRole('button', { name: 'Añadir miembro' }).click();
  await expect(page.getByRole('cell', { name: username, exact: true })).toBeVisible();

  // Lector: ve el historial, pero no lanza ni tiene las pestañas de editor.
  const member = await browser.newPage();
  await login(member, username, password);
  await member.goto(projectUrl);
  await expect(member.getByRole('heading', { name: project })).toBeVisible();
  await expect(member.getByText('Lector')).toBeVisible();
  await expect(member.getByRole('button', { name: 'Lanzar ejecución' })).toHaveCount(0);
  await expect(member.getByRole('tab', { name: 'Carga' })).toHaveCount(0);
  await expect(member.getByRole('tab', { name: 'Ajustes' })).toHaveCount(0);
  // Pedir la pestaña por URL no salta el rol.
  await member.goto(`${projectUrl}?tab=bulk`);
  await expect(member.getByRole('tab', { name: 'Ejecuciones', selected: true })).toBeVisible();

  // Editor: ya lanza; los ajustes siguen siendo del propietario.
  await page.getByRole('combobox', { name: `Rol de ${username}` }).click();
  await page.getByRole('option', { name: 'Editor' }).click();
  await expect(page.getByRole('combobox', { name: `Rol de ${username}` })).toHaveValue('Editor');
  await member.goto(projectUrl);
  await expect(member.getByRole('button', { name: 'Lanzar ejecución' })).toBeVisible();
  await expect(member.getByRole('tab', { name: 'Carga' })).toBeVisible();
  await expect(member.getByRole('tab', { name: 'Ajustes' })).toHaveCount(0);
  await member.close();

  // Limpieza: el proyecto (el usuario queda, como en login.spec.ts).
  await page.getByRole('tab', { name: 'Ajustes' }).click();
  await page.getByRole('button', { name: 'Borrar proyecto' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Borrar' }).click();
  await expect(page).toHaveURL(/\/projects$/);
});
