import { expect, type Page, test } from './fixtures';

// Requiere el admin E2E (ver login.spec.ts) y el worker en marcha (`docker compose up` arranca web y worker).
const ADMIN_USER = process.env.UBW_E2E_ADMIN_USER;
const ADMIN_PASSWORD = process.env.UBW_E2E_ADMIN_PASSWORD;

test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define UBW_E2E_ADMIN_USER y UBW_E2E_ADMIN_PASSWORD');

async function login(page: Page) {
  await page.goto('/login');
  await page.getByLabel('Usuario').fill(ADMIN_USER ?? '');
  await page.getByLabel('Contraseña').fill(ADMIN_PASSWORD ?? '');
  await page.getByRole('button', { name: 'Iniciar sesión' }).click();
  await expect(page.getByRole('button', { name: /Menú de usuario/ })).toBeVisible();
}

test('crear proyecto, lanzar noop, seguir el progreso, ver artefactos, ZIP, relanzar y borrar', async ({
  page,
}) => {
  test.setTimeout(120_000);
  const name = `e2e-proyecto-${Date.now()}`;
  await login(page);

  await page.getByRole('link', { name: 'Proyectos' }).click();
  await page.getByRole('button', { name: 'Nuevo proyecto' }).click();
  await page
    .getByRole('dialog')
    .getByRole('textbox', { name: /^Nombre/ })
    .fill(name);
  await page.getByRole('dialog').getByRole('button', { name: 'Crear proyecto' }).click();
  await expect(page.getByRole('heading', { name })).toBeVisible();

  await page.getByRole('button', { name: 'Lanzar ejecución' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('textbox', { name: 'Pasos' }).fill('4');
  await dialog.getByRole('textbox', { name: 'Segundos por paso' }).fill('1');
  await dialog.getByRole('button', { name: 'Lanzar' }).click();

  // Progreso en vivo por SSE: aparece algún paso intermedio y termina en «Correcta».
  await expect(page.getByRole('heading', { name: 'Ejecución noop' })).toBeVisible();
  await expect(page.getByText(/Paso \d de 4/)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('Correcta')).toBeVisible({ timeout: 60_000 });

  const iframe = page.getByTitle('Vista previa de outputs/html/resumen.html');
  await expect(iframe).toHaveAttribute('sandbox', '');
  // El script del HTML de ejemplo no se ejecuta: el iframe no tiene allow-scripts y la API envía CSP sandbox.
  await expect(
    page.frameLocator('iframe[title^="Vista previa"]').getByRole('heading', { name: /Ejecución/ }),
  ).toBeVisible();

  await page.getByText('ejemplo.sql').click();
  await expect(page.getByText('SELECT 1 AS ok;')).toBeVisible();

  const download = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Descargar ZIP' }).click();
  expect((await download).suggestedFilename()).toMatch(/_noop_[0-9A-Z]{26}\.zip$/);

  await page.getByRole('button', { name: 'Relanzar' }).click();
  await expect(page.getByText('Relanzada de')).toBeVisible();
  await expect(page.getByText('Correcta')).toBeVisible({ timeout: 60_000 });

  await page.getByRole('link', { name }).click();
  await expect(page.getByRole('row')).toHaveCount(3); // cabecera + 2 ejecuciones
  await page.getByRole('tab', { name: 'Ajustes' }).click();
  await page.getByRole('button', { name: 'Borrar proyecto' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Borrar' }).click();
  await expect(page.getByRole('heading', { name: 'Proyectos' })).toBeVisible();
  await expect(page.getByRole('link', { name })).toHaveCount(0);
});

test('cancelar una ejecución en curso', async ({ page }) => {
  test.setTimeout(90_000);
  const name = `e2e-cancelar-${Date.now()}`;
  await login(page);
  await page.goto('/projects');
  await page.getByRole('button', { name: 'Nuevo proyecto' }).click();
  await page
    .getByRole('dialog')
    .getByRole('textbox', { name: /^Nombre/ })
    .fill(name);
  await page.getByRole('dialog').getByRole('button', { name: 'Crear proyecto' }).click();

  await page.getByRole('button', { name: 'Lanzar ejecución' }).click();
  await page.getByRole('dialog').getByRole('textbox', { name: 'Pasos' }).fill('20');
  await page.getByRole('dialog').getByRole('textbox', { name: 'Segundos por paso' }).fill('3');
  await page.getByRole('dialog').getByRole('button', { name: 'Lanzar' }).click();
  await expect(page.getByText(/Paso \d+ de 20/)).toBeVisible({ timeout: 30_000 });

  await page.getByRole('button', { name: 'Cancelar' }).click();
  await expect(page.getByText('Cancelada por un usuario.')).toBeVisible({ timeout: 30_000 });

  await page.getByRole('link', { name }).click();
  await page.getByRole('tab', { name: 'Ajustes' }).click();
  await page.getByRole('button', { name: 'Borrar proyecto' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Borrar' }).click();
  await expect(page.getByRole('heading', { name: 'Proyectos' })).toBeVisible();
});
