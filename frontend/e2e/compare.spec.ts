import { expect, type Locator, type Page, test } from '@playwright/test';

// Requisitos de explorer.spec.ts y, además, la segunda BD en el contenedor:
//   python -c "import sqlite3; c=sqlite3.connect('e2e-tienda-v2.db'); c.executescript(open('e2e/fixtures/tienda_v2.sql').read())"
//   docker compose cp e2e-tienda-v2.db web:/data/files/e2e-tienda-v2.db
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

async function createConnection(page: Page, name: string, file: string): Promise<string> {
  await page.goto('/connections/new?db_type=sqlite');
  await page.getByRole('textbox', { name: /^Nombre/ }).fill(name);
  await page.getByRole('textbox', { name: /^database/ }).fill(file);
  await page.getByRole('button', { name: 'Crear conexión' }).click();
  await expect(page.getByRole('heading', { name })).toBeVisible();
  return page.url();
}

async function associate(page: Page, connection: string, alias: string) {
  await page.getByRole('tab', { name: 'Conexiones' }).click();
  await page.getByRole('combobox', { name: 'Conexión' }).selectOption({ label: `${connection} (sqlite)` });
  await page.getByRole('textbox', { name: /^Alias/ }).fill(alias);
  await page.getByRole('button', { name: 'Asociar' }).click();
  await expect(page.getByRole('cell', { name: alias, exact: true })).toBeVisible();
}

async function launchCompare(page: Page, projectUrl: string) {
  await page.goto(projectUrl);
  await page.getByRole('tab', { name: 'Ejecuciones' }).click();
  await page.getByRole('button', { name: 'Lanzar ejecución' }).click();
  const dialog: Locator = page.getByRole('dialog');
  await dialog
    .getByRole('combobox', { name: 'Operación' })
    .selectOption({ label: 'Comparación de esquemas' });
  await dialog.getByRole('combobox', { name: 'Conexión origen' }).selectOption('v2');
  await dialog.getByRole('combobox', { name: 'Conexión destino' }).selectOption('v1');
  await dialog.getByRole('button', { name: 'Lanzar' }).click();
  await expect(page).toHaveURL(/\/runs\//);
  await expect(page.getByText('Correcta', { exact: true })).toBeVisible({ timeout: 120_000 });
}

test('comparar dos BD SQLite, navegar por el diff y ver la evolución', async ({ page }) => {
  test.setTimeout(240_000);
  const stamp = Date.now();
  const [v1, v2, project] = [`e2e-cmp-v1-${stamp}`, `e2e-cmp-v2-${stamp}`, `e2e-cmp-${stamp}`];
  await login(page);
  const v1Url = await createConnection(page, v1, 'e2e-tienda.db');
  const v2Url = await createConnection(page, v2, 'e2e-tienda-v2.db');

  await page.goto('/projects');
  await page.getByRole('button', { name: 'Nuevo proyecto' }).click();
  await page
    .getByRole('dialog')
    .getByRole('textbox', { name: /^Nombre/ })
    .fill(project);
  await page.getByRole('dialog').getByRole('button', { name: 'Crear proyecto' }).click();
  await expect(page.getByRole('heading', { name: project })).toBeVisible();
  const projectUrl = page.url();
  await associate(page, v1, 'v1');
  await associate(page, v2, 'v2');

  // Primera comparación: visor navegable, informe HTML aislado y descargas.
  await launchCompare(page, projectUrl);
  await expect(page.getByRole('heading', { name: 'Diferencias de esquema' })).toBeVisible();
  await expect(page.getByRole('tab', { name: 'Tablas (3)' })).toBeVisible();
  await page.getByRole('button', { name: /clientes/ }).click();
  await expect(page.getByRole('cell', { name: 'email' })).toBeVisible();
  await page.getByRole('button', { name: /pedidos/ }).click();
  await expect(page.getByRole('cell', { name: 'ix_pedidos_cliente' })).toBeVisible();
  await page.getByRole('tab', { name: 'Vistas (1)' }).click();
  await page.getByRole('button', { name: /v_pedidos/ }).click();
  await expect(page.getByRole('table', { name: /Definición/ })).toContainText('p.total');
  await expect(page.getByText('El script SQL no se ha ejecutado')).toBeVisible();
  const report = page.frameLocator('iframe[title="Informe HTML de la comparación"]');
  await expect(report.locator('code', { hasText: /^facturas$/ }).first()).toBeVisible({ timeout: 30_000 });
  // El script del informe arranca con el sustituto local de Mermaid (G25), sin salir a Internet y en origen opaco.
  const frame = page.frames().find((f) => f.url().includes('/comparacion/index.html'));
  expect(await frame?.evaluate('[typeof window.mermaid, window.origin]')).toEqual(['object', 'null']);
  await expect(page.getByRole('link', { name: /Descargar comparacion\.sql/ })).toBeVisible();

  // Segunda comparación y evolución respecto a la primera (los esquemas no han cambiado).
  await launchCompare(page, projectUrl);
  await page.getByRole('combobox', { name: 'Comparación anterior' }).selectOption({ index: 1 });
  await expect(page.getByRole('table', { name: 'Siguen' })).toContainText('facturas');
  await expect(page.getByText('Origen o destino distintos')).toHaveCount(0);

  // Limpieza.
  await page.goto(projectUrl);
  await page.getByRole('tab', { name: 'Ajustes' }).click();
  await page.getByRole('button', { name: 'Borrar proyecto' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Borrar' }).click();
  for (const url of [v1Url, v2Url]) {
    await page.goto(url);
    await page.getByRole('button', { name: 'Borrar' }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Borrar' }).click();
    await expect(page.getByRole('heading', { name: 'Conexiones' })).toBeVisible();
  }
});
