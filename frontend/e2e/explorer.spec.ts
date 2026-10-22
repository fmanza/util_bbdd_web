import { expect, type Page, test } from '@playwright/test';

// Requiere el admin E2E (ver login.spec.ts) y una BD SQLite de ejemplo en el contenedor:
//   python -c "import sqlite3; c=sqlite3.connect('e2e-tienda.db'); c.executescript(open('e2e/fixtures/tienda.sql').read())"
//   docker compose cp e2e-tienda.db web:/data/files/e2e-tienda.db
// y UBW_E2E_SQLITE=1.
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

async function setOwnSqlPermission(page: Page, value: boolean) {
  await page.goto('/admin/users');
  await page.getByRole('button', { name: `Editar ${ADMIN_USER}` }).click();
  const dialog = page.getByRole('dialog');
  const toggle = dialog.getByRole('switch', { name: /Puede ejecutar SQL libre/ });
  if ((await toggle.isChecked()) !== value) {
    await toggle.click({ force: true });
  }
  await dialog.getByRole('button', { name: 'Guardar' }).click();
  await expect(dialog).toBeHidden();
}

test('explorar una BD SQLite, queries nombradas y SQL libre de solo lectura', async ({ page }) => {
  test.setTimeout(120_000);
  const stamp = Date.now();
  const connection = `e2e-tienda-${stamp}`;
  const queryName = `e2e_pedidos_${stamp}`;
  const project = `e2e-sql-${stamp}`;
  await login(page);

  // Conexión SQLite y explorador.
  await page.goto('/connections/new?db_type=sqlite');
  await page.getByRole('textbox', { name: /^Nombre/ }).fill(connection);
  await page.getByRole('textbox', { name: /^database/ }).fill('e2e-tienda.db');
  await page.getByRole('button', { name: 'Crear conexión' }).click();
  await expect(page.getByRole('heading', { name: connection })).toBeVisible();
  const connectionUrl = page.url();
  await page.getByRole('link', { name: 'Explorar' }).click();
  await page.getByText('pedidos', { exact: true }).click();
  await expect(page.getByRole('tab', { name: 'Columnas (3)' })).toBeVisible({ timeout: 30_000 });
  await page.getByRole('tab', { name: /Relaciones/ }).click();
  await expect(page.getByRole('button', { name: 'clientes' })).toBeVisible();
  await page.getByRole('tab', { name: 'DDL' }).click();
  await expect(page.getByText(/CREATE TABLE pedidos/)).toBeVisible({ timeout: 30_000 });

  // Query nombrada (admin) y ejecución desde el explorador.
  await page.goto('/admin/queries');
  await page.getByRole('button', { name: 'Nueva query' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('combobox', { name: 'Motor' }).selectOption('sqlite');
  await dialog.getByRole('textbox', { name: /^Nombre/ }).fill(queryName);
  await dialog
    .getByRole('textbox', { name: /^Plantilla SQL/ })
    .fill('SELECT id, total FROM pedidos WHERE cliente_id = {cliente} ORDER BY id');
  await dialog.getByRole('button', { name: 'Guardar' }).click();
  await expect(page.getByText(queryName)).toBeVisible();
  await page.goto(`${connectionUrl}/explore`);
  await page.getByRole('tab', { name: 'Queries nombradas' }).click();
  await page.getByRole('combobox', { name: 'Query' }).selectOption({ label: queryName });
  await page.getByRole('textbox', { name: /^cliente/ }).fill('1');
  await page.getByRole('button', { name: 'Ejecutar' }).click();
  await expect(page.getByText('2 filas', { exact: false })).toBeVisible({ timeout: 30_000 });

  // SQL libre: permiso propio, proyecto con la conexión y consultas.
  await setOwnSqlPermission(page, true);
  await page.goto('/projects');
  await page.getByRole('button', { name: 'Nuevo proyecto' }).click();
  await page
    .getByRole('dialog')
    .getByRole('textbox', { name: /^Nombre/ })
    .fill(project);
  await page.getByRole('dialog').getByRole('button', { name: 'Crear proyecto' }).click();
  await page.getByRole('tab', { name: 'Conexiones' }).click();
  await page.getByRole('combobox', { name: 'Conexión' }).selectOption({ label: `${connection} (sqlite)` });
  await page.getByRole('textbox', { name: /^Alias/ }).fill('tienda');
  await page.getByRole('button', { name: 'Asociar' }).click();
  await expect(page.getByRole('cell', { name: 'tienda', exact: true })).toBeVisible();
  await page.getByRole('tab', { name: 'SQL' }).click();
  const editor = page.getByRole('textbox', { name: /^Consulta/ });
  await editor.fill(
    'SELECT c.nombre, COUNT(*) AS n FROM pedidos p JOIN clientes c ON c.id = p.cliente_id GROUP BY c.nombre',
  );
  await page.getByRole('button', { name: 'Ejecutar' }).click();
  await expect(page.getByRole('cell', { name: 'ana' })).toBeVisible({ timeout: 30_000 });
  await editor.fill('DELETE FROM pedidos');
  await page.getByRole('button', { name: 'Ejecutar' }).click();
  await expect(page.getByRole('alert')).toContainText('Solo se admiten consultas SELECT');

  // Limpieza.
  await page.getByRole('tab', { name: 'Ajustes' }).click();
  await page.getByRole('button', { name: 'Borrar proyecto' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Borrar' }).click();
  await setOwnSqlPermission(page, false);
  await page.goto('/admin/queries');
  await page.getByRole('button', { name: `Borrar ${queryName}` }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Borrar' }).click();
  await page.goto(connectionUrl);
  await page.getByRole('button', { name: 'Borrar' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Borrar' }).click();
  await expect(page.getByRole('heading', { name: 'Conexiones' })).toBeVisible();
});
