import { expect, type Page, test } from './fixtures';

// Almacenamiento administrable (ADR-012). Requiere el admin E2E (ver login.spec.ts). Solo toca un ajuste inofensivo
// (alarga la retención de ficheros un día y la restablece) para no afectar a otros specs en paralelo.
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

test('el admin cambia y restablece un ajuste y da una cuota propia que el usuario ve', async ({
  page,
  browser,
}) => {
  const username = `e2e-quota-${Date.now()}`;
  const password = 'frase-de-paso-e2e-1234';
  await login(page, ADMIN_USER ?? '', ADMIN_PASSWORD ?? '');

  // Ajuste: más días de retención de ficheros (no purga nada), con confirmación y después restablecido.
  await page.goto('/admin/storage');
  const retention = page.getByRole('textbox', { name: 'Retención de ficheros de carga (días)' });
  await expect(retention).toBeVisible();
  const current = Number(await retention.inputValue());
  await retention.fill(String(current + 1));
  await page.getByRole('button', { name: 'Guardar' }).click();
  const confirm = page.getByRole('dialog', { name: 'Confirmar los ajustes' });
  await expect(confirm.getByText('Con estos ajustes no se purgará nada ahora.')).toBeVisible();
  await confirm.getByRole('button', { name: 'Guardar' }).click();
  await expect(confirm).toBeHidden();
  await page.reload();
  await expect(retention).toHaveValue(String(current + 1));
  await page.getByRole('button', { name: 'Restablecer Retención de ficheros de carga (días)' }).click();
  await page.getByRole('button', { name: 'Guardar' }).click();
  await confirm.getByRole('button', { name: 'Guardar' }).click();
  await expect(confirm).toBeHidden();
  await expect(page.getByRole('table', { name: 'Uso por usuario' })).toBeVisible();

  // Usuario con cuota propia.
  await page.goto('/admin/users');
  await page.getByRole('button', { name: 'Nuevo usuario' }).click();
  let dialog = page.getByRole('dialog');
  await dialog.getByRole('textbox', { name: /^Usuario/ }).fill(username);
  await dialog.getByRole('textbox', { name: /Nombre visible/ }).fill('Cuota E2E');
  await dialog.getByLabel(/^Contraseña/).fill(password);
  await dialog.getByRole('button', { name: 'Crear usuario' }).click();
  await expect(dialog).toBeHidden();
  await page.getByRole('button', { name: `Editar ${username}` }).click();
  dialog = page.getByRole('dialog');
  await dialog.getByRole('switch', { name: /Usar la cuota global/ }).click({ force: true });
  await dialog.getByRole('textbox', { name: /Cuota propia/ }).fill('2048');
  await dialog.getByRole('button', { name: 'Guardar' }).click();
  await expect(dialog).toBeHidden();

  const context = await browser.newContext();
  const other = await context.newPage();
  await login(other, username, password);
  await other.getByRole('button', { name: /Menú de usuario/ }).click();
  await other.getByRole('menuitem', { name: 'Mi espacio' }).click();
  await expect(other.getByRole('heading', { name: 'Mi espacio' })).toBeVisible();
  await expect(other.getByText('Cuota asignada a tu cuenta.')).toBeVisible();
  // Al 0 % la barra no tiene ancho (Playwright la da por oculta): se comprueba su valor.
  await expect(other.getByRole('progressbar', { name: '0 % de tu cuota' })).toHaveAttribute(
    'aria-valuenow',
    '0',
  );
  await context.close();
});
