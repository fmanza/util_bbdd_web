import { expect, type Page, test } from './fixtures';

// Mismos requisitos que explorer.spec.ts: admin E2E, `e2e-tienda.db` copiada al contenedor y UBW_E2E_SQLITE=1.
const ADMIN_USER = process.env.UBW_E2E_ADMIN_USER;
const ADMIN_PASSWORD = process.env.UBW_E2E_ADMIN_PASSWORD;

test.skip(
  !ADMIN_USER || !ADMIN_PASSWORD || !process.env.UBW_E2E_SQLITE,
  'Define el admin E2E y UBW_E2E_SQLITE=1',
);

async function login(page: Page) {
  await page.goto('/login');
  await page.getByLabel('Usuario').fill(ADMIN_USER ?? '');
  await page.getByLabel('Contraseña').fill(ADMIN_PASSWORD ?? '');
  await page.getByRole('button', { name: 'Iniciar sesión' }).click();
  await expect(page.getByRole('button', { name: /Menú de usuario/ })).toBeVisible();
}

async function launch(
  page: Page,
  operation: string,
  fill?: (dialog: ReturnType<Page['getByRole']>) => Promise<void>,
) {
  await page.getByRole('tab', { name: 'Ejecuciones' }).click();
  await page.getByRole('button', { name: 'Lanzar ejecución' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('combobox', { name: 'Operación' }).selectOption({ label: operation });
  await dialog.getByRole('combobox', { name: 'Conexión' }).selectOption('tienda');
  if (fill) await fill(dialog);
  await dialog.getByRole('button', { name: 'Lanzar' }).click();
  await expect(page).toHaveURL(/\/runs\//);
  await expect(page.getByText('Correcta')).toBeVisible({ timeout: 120_000 });
}

test('documentar una BD SQLite y ver su grafo de relaciones', async ({ page }) => {
  test.setTimeout(240_000);
  const stamp = Date.now();
  const connection = `e2e-doc-${stamp}`;
  const project = `e2e-doc-${stamp}`;
  await login(page);

  await page.goto('/connections/new?db_type=sqlite');
  await page.getByRole('textbox', { name: /^Nombre/ }).fill(connection);
  await page.getByRole('textbox', { name: /^database/ }).fill('e2e-tienda.db');
  await page.getByRole('button', { name: 'Crear conexión' }).click();
  await expect(page.getByRole('heading', { name: connection })).toBeVisible();
  const connectionUrl = page.url();

  await page.goto('/projects');
  await page.getByRole('button', { name: 'Nuevo proyecto' }).click();
  await page
    .getByRole('dialog')
    .getByRole('textbox', { name: /^Nombre/ })
    .fill(project);
  await page.getByRole('dialog').getByRole('button', { name: 'Crear proyecto' }).click();
  await expect(page.getByRole('heading', { name: project })).toBeVisible();
  const projectUrl = page.url();
  await page.getByRole('tab', { name: 'Conexiones' }).click();
  await page.getByRole('combobox', { name: 'Conexión' }).selectOption({ label: `${connection} (sqlite)` });
  await page.getByRole('textbox', { name: /^Alias/ }).fill('tienda');
  await page.getByRole('button', { name: 'Asociar' }).click();
  await expect(page.getByRole('cell', { name: 'tienda', exact: true })).toBeVisible();

  // Documentación: Word, Excel y sitio HTML con scripts en un iframe de origen opaco.
  await launch(page, 'Documentación de la base de datos');
  await expect(page.getByRole('link', { name: /Descargar .*\.docx/ })).toBeVisible();
  await expect(page.getByRole('link', { name: /Descargar .*\.xlsx/ })).toBeVisible();
  const site = page.frameLocator('iframe[title="Sitio HTML de la documentación"]');
  await expect(site.getByText('pedidos').first()).toBeVisible({ timeout: 30_000 });
  const frame = page.frames().find((f) => f.url().includes('/site/'));
  expect(frame).toBeDefined();
  // Se evalúa dentro del sitio: su origen es opaco, no puede leer la cookie ni el documento de la SPA.
  const isolation: unknown = await frame?.evaluate(`(() => {
    let cookie;
    try { cookie = document.cookie; } catch { cookie = 'blocked'; }
    let parentReadable;
    try { parentReadable = Boolean(window.parent.document); } catch { parentReadable = false; }
    return { origin: window.origin, cookie, parentReadable };
  })()`);
  expect(isolation).toEqual({ origin: 'null', cookie: 'blocked', parentReadable: false });

  // Grafo de una tabla.
  await page.goto(projectUrl);
  await launch(page, 'Grafo de relaciones', async (dialog) => {
    await dialog.getByRole('textbox', { name: /^Tabla central/ }).fill('pedidos');
  });
  await expect(page.getByRole('img', { name: /Grafo de relaciones .*pedidos/ }).first()).toBeVisible();

  // Limpieza.
  await page.goto(projectUrl);
  await page.getByRole('tab', { name: 'Ajustes' }).click();
  await page.getByRole('button', { name: 'Borrar proyecto' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Borrar' }).click();
  await page.goto(connectionUrl);
  await page.getByRole('button', { name: 'Borrar' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Borrar' }).click();
  await expect(page.getByRole('heading', { name: 'Conexiones' })).toBeVisible();
});
