import { expect, type Page, test } from '@playwright/test';

// Volcado SQLite → SQLite (no necesita el bench). Requiere el admin E2E, UBW_E2E_SQLITE=1 y, en el contenedor, las BD
// de e2e/fixtures/volcado.sql (origen) y volcado_vacio.sql (destino):
//   python -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.executescript(open(sys.argv[2]).read())" e2e-volcado-origen.db e2e/fixtures/volcado.sql
//   docker compose cp e2e-volcado-origen.db web:/data/files/e2e-volcado-origen.db   (y lo mismo con el destino)
//   docker compose exec web sh -c 'cd /data/files && cp e2e-volcado-destino.db x && mv -f x e2e-volcado-destino.db'
//   (docker cp deja el fichero como root y el contenedor no tiene CAP_CHOWN: así pasa a ser del usuario app)
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

async function setOwnPermission(page: Page, value: boolean) {
  await page.goto('/admin/users');
  await page.getByRole('button', { name: `Editar ${ADMIN_USER}` }).click();
  const dialog = page.getByRole('dialog');
  const toggle = dialog.getByRole('switch', { name: /Puede volcar datos/ });
  if ((await toggle.isChecked()) !== value) {
    await toggle.click({ force: true });
  }
  await dialog.getByRole('button', { name: 'Guardar' }).click();
  await expect(dialog).toBeHidden();
}

async function createConnection(page: Page, name: string, file: string, readOnly: boolean): Promise<string> {
  await page.goto('/connections/new?db_type=sqlite');
  await page.getByRole('textbox', { name: /^Nombre/ }).fill(name);
  await page.getByRole('textbox', { name: /^database/ }).fill(file);
  const readOnlySwitch = page.getByRole('switch', { name: /^Solo lectura/ });
  if ((await readOnlySwitch.isChecked()) !== readOnly) {
    await readOnlySwitch.click({ force: true });
  }
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

/** Espera a la ejecución recién lanzada (otra URL que `from`) y a su estado. */
async function waitStatus(page: Page, status: string, from: string) {
  await expect(page).not.toHaveURL(from);
  await expect(page).toHaveURL(/\/runs\//);
  await expect(page.getByText(status, { exact: true }).first()).toBeVisible({ timeout: 120_000 });
}

async function preview(page: Page, projectUrl: string, truncate: boolean): Promise<string> {
  await page.goto(projectUrl);
  await page.getByRole('tab', { name: 'Ejecuciones' }).click();
  await page.getByRole('button', { name: 'Lanzar ejecución' }).click();
  const dialog = page.getByRole('dialog');
  await dialog
    .getByRole('combobox', { name: 'Operación' })
    .selectOption({ label: 'Volcado de datos: vista previa' });
  await dialog.getByRole('combobox', { name: 'Conexión origen' }).selectOption('origen');
  await dialog.getByRole('combobox', { name: 'Conexión destino' }).selectOption('destino');
  if (truncate) {
    await dialog.getByRole('switch', { name: /Vaciar el destino/ }).click({ force: true });
  }
  await dialog.getByRole('button', { name: 'Lanzar' }).click();
  await waitStatus(page, 'Correcta', projectUrl);
  await expect(page.getByRole('table', { name: 'Orden de carga' })).toBeVisible();
  return page.url();
}

async function dump(page: Page, previewUrl: string, truncate: boolean) {
  await page
    .getByRole('button', { name: truncate ? /Vaciar y volcar en «destino»/ : /Volcar en «destino»/ })
    .click();
  const confirm = page.getByRole('dialog');
  await confirm.getByRole('checkbox', { name: /He revisado la vista previa/ }).check();
  await confirm.getByRole('textbox', { name: 'Escribe «destino» para confirmar' }).fill('destino');
  if (truncate) {
    await confirm.getByRole('textbox', { name: /Escribe «VACIAR»/ }).fill('VACIAR');
  }
  await confirm.getByRole('button', { name: 'Volcar ahora' }).click();
  await waitStatus(page, 'Correcta', previewUrl);
}

test('vista previa y volcado SQLite → SQLite, vaciando y después añadiendo', async ({ page }) => {
  // Escribe en un fichero compartido del contenedor: la copia de --repeat-each se pisaría con la primera.
  test.skip(test.info().repeatEachIndex > 0, 'Escribe en un destino compartido');
  test.setTimeout(240_000);
  const stamp = Date.now();
  const [src, dst, project] = [`e2e-dump-src-${stamp}`, `e2e-dump-dst-${stamp}`, `e2e-dump-${stamp}`];
  await login(page);
  await setOwnPermission(page, true);
  const srcUrl = await createConnection(page, src, 'e2e-volcado-origen.db', true);
  const dstUrl = await createConnection(page, dst, 'e2e-volcado-destino.db', false);
  await page.goto('/projects');
  await page.getByRole('button', { name: 'Nuevo proyecto' }).click();
  await page
    .getByRole('dialog')
    .getByRole('textbox', { name: /^Nombre/ })
    .fill(project);
  await page.getByRole('dialog').getByRole('button', { name: 'Crear proyecto' }).click();
  await expect(page.getByRole('heading', { name: project })).toBeVisible();
  const projectUrl = page.url();
  await associate(page, src, 'origen');
  await associate(page, dst, 'destino');

  // Vaciando (el destino puede tener filas de una ejecución anterior del E2E).
  const first = await preview(page, projectUrl, true);
  await expect(page.getByText('Vacía el destino')).toBeVisible();
  await dump(page, first, true);
  const result = page.getByRole('table', { name: 'Tablas volcadas' });
  await expect(result.getByRole('row', { name: /clientes/ })).toContainText('Correcta');
  await expect(result.getByRole('row', { name: /pedidos/ })).toContainText('3');
  await expect(page.getByRole('button', { name: 'Relanzar' })).toHaveCount(0);

  // Añadiendo: la vista previa avisa de que el destino ya tiene filas.
  await preview(page, projectUrl, false);
  await expect(page.getByText(/ya tiene filas en clientes, pedidos: se añadirán/)).toBeVisible();

  // Limpieza.
  await page.goto(projectUrl);
  await page.getByRole('tab', { name: 'Ajustes' }).click();
  await page.getByRole('button', { name: 'Borrar proyecto' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Borrar' }).click();
  for (const url of [srcUrl, dstUrl]) {
    await page.goto(url);
    await page.getByRole('button', { name: 'Borrar' }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Borrar' }).click();
    await expect(page.getByRole('heading', { name: 'Conexiones' })).toBeVisible();
  }
  await setOwnPermission(page, false);
});
