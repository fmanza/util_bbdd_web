import { expect, type Page, test } from './fixtures';

// Carga bulk en SQLite (no necesita el bench). Requiere el admin E2E, UBW_E2E_SQLITE=1 y, en el contenedor, la BD
// e2e-carga.db creada con el esquema de e2e/fixtures/volcado_vacio.sql:
//   python -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.executescript(open(sys.argv[2]).read())" e2e-carga.db e2e/fixtures/volcado_vacio.sql
//   docker compose cp e2e-carga.db web:/data/files/e2e-carga.db
//   docker compose exec web sh -c 'cd /data/files && cp e2e-carga.db x && mv -f x e2e-carga.db'
// Inserta dos filas con claves únicas por ejecución y las borra después: la tabla queda como estaba.
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
  const toggle = dialog.getByRole('switch', { name: /Puede escribir datos/ });
  if ((await toggle.isChecked()) !== value) {
    await toggle.click({ force: true });
  }
  await dialog.getByRole('button', { name: 'Guardar' }).click();
  await expect(dialog).toBeHidden();
}

/** Espera a la ejecución recién lanzada (otra URL que `from`) y a su estado. */
async function waitStatus(page: Page, status: string, from: string) {
  await expect(page).not.toHaveURL(from);
  await expect(page).toHaveURL(/\/runs\//);
  await expect(page.getByText(status, { exact: true }).first()).toBeVisible({ timeout: 120_000 });
}

async function previewLoad(page: Page, projectUrl: string, file: string, operation: string): Promise<string> {
  await page.goto(`${projectUrl}?tab=bulk`);
  await page.getByRole('combobox', { name: 'Fichero', exact: true }).selectOption({ label: file });
  await page.getByRole('combobox', { name: 'Operación' }).selectOption({ label: operation });
  await page.getByRole('combobox', { name: 'Conexión destino' }).selectOption('destino');
  await page.getByRole('textbox', { name: 'Tabla destino' }).fill('clientes');
  await expect(page.getByRole('textbox', { name: 'Columna de la tabla para «id»' })).toHaveValue('id');
  await page.getByRole('button', { name: 'Vista previa' }).click();
  await waitStatus(page, 'Correcta', `${projectUrl}?tab=bulk`);
  await expect(page.getByRole('heading', { name: 'Vista previa de la carga' })).toBeVisible();
  return page.url();
}

async function apply(page: Page, previewUrl: string, button: RegExp, rows: number | null) {
  await page.getByRole('button', { name: button }).click();
  const confirm = page.getByRole('dialog');
  await confirm.getByRole('checkbox', { name: /He revisado la vista previa/ }).check();
  await confirm.getByRole('textbox', { name: 'Escribe «destino» para confirmar' }).fill('destino');
  if (rows !== null) {
    await confirm.getByRole('textbox', { name: 'Escribe el número de filas afectadas' }).fill(String(rows));
  }
  await confirm.getByRole('button', { name: 'Cargar ahora' }).click();
  await waitStatus(page, 'Correcta', previewUrl);
}

test('sube un CSV, lo inserta y borra las mismas filas con confirmación', async ({ page }) => {
  // Escribe en un fichero compartido del contenedor: la copia de --repeat-each se pisaría con la primera.
  test.skip(test.info().repeatEachIndex > 0, 'Escribe en un destino compartido');
  test.setTimeout(240_000);
  const stamp = Date.now();
  const [connection, project, file] = [`e2e-bulk-${stamp}`, `e2e-bulk-${stamp}`, `clientes-${stamp}.csv`];
  const base = stamp % 1_000_000_000;
  const csv = `id;nombre\n${base};Cliente ${stamp} A\n${base + 1};Cliente ${stamp} B\n`;

  await login(page);
  await setOwnPermission(page, true);
  await page.goto('/connections/new?db_type=sqlite');
  await page.getByRole('textbox', { name: /^Nombre/ }).fill(connection);
  await page.getByRole('textbox', { name: /^database/ }).fill('e2e-carga.db');
  const readOnly = page.getByRole('switch', { name: /^Solo lectura/ });
  if (await readOnly.isChecked()) {
    await readOnly.click({ force: true });
  }
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
  await page.getByRole('textbox', { name: /^Alias/ }).fill('destino');
  await page.getByRole('button', { name: 'Asociar' }).click();
  await expect(page.getByRole('cell', { name: 'destino', exact: true })).toBeVisible();

  // Subida del fichero.
  await page.getByRole('tab', { name: 'Carga' }).click();
  await page
    .locator('input[type="file"]')
    .setInputFiles({ name: file, mimeType: 'text/csv', buffer: Buffer.from(csv, 'utf-8') });
  await page.getByRole('button', { name: 'Subir' }).click();
  await expect(page.getByRole('cell', { name: file, exact: true })).toBeVisible();

  // Insertar: la vista previa genera el SQL sin tocar el destino.
  const insert = await previewLoad(page, projectUrl, file, 'Insertar');
  await expect(page.getByText(/INSERT INTO/).first()).toBeVisible();
  await apply(page, insert, /Insertar en «destino»/, null);
  await expect(page.getByRole('heading', { name: 'Resultado de la carga' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Relanzar' })).toHaveCount(0);

  // Borrar: exige escribir las 2 filas afectadas.
  const remove = await previewLoad(page, projectUrl, file, 'Borrar');
  await expect(page.getByText('Filas que se borrarán')).toBeVisible();
  await apply(page, remove, /Borrar en «destino»/, 2);
  await expect(page.getByRole('heading', { name: 'Resultado de la carga' })).toBeVisible();

  // Limpieza.
  await page.goto(projectUrl);
  await page.getByRole('tab', { name: 'Ajustes' }).click();
  await page.getByRole('button', { name: 'Borrar proyecto' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Borrar' }).click();
  await page.goto(connectionUrl);
  await page.getByRole('button', { name: 'Borrar' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Borrar' }).click();
  await expect(page.getByRole('heading', { name: 'Conexiones' })).toBeVisible();
  await setOwnPermission(page, false);
});
