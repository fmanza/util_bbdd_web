import { expect, type Page, test } from '@playwright/test';

// Migración DDL real entre los contenedores bench (PostgreSQL → MySQL). Requiere el admin E2E,
// UTIL_BBDD_BENCH_PASSWORD, UBW_E2E_MIGRATE=1 y, antes, las tablas de origen (y la limpieza después), desde backend/:
//   uv run python -m tests.integration.e2e_migrate_fixture setup
//   uv run python -m tests.integration.e2e_migrate_fixture teardown
// Escribe en el bench MySQL: no se ejecuta con --repeat-each (la segunda copia encontraría las tablas).
const ADMIN_USER = process.env.UBW_E2E_ADMIN_USER;
const ADMIN_PASSWORD = process.env.UBW_E2E_ADMIN_PASSWORD;
const BENCH_PASSWORD = process.env.UTIL_BBDD_BENCH_PASSWORD;
const PG_PORT = process.env.UTIL_BBDD_BENCH_POSTGRES_PORT ?? '55432';
const MYSQL_PORT = process.env.UTIL_BBDD_BENCH_MYSQL_PORT ?? '53306';

test.skip(
  !ADMIN_USER || !ADMIN_PASSWORD || !BENCH_PASSWORD || !process.env.UBW_E2E_MIGRATE,
  'Define el admin E2E, UTIL_BBDD_BENCH_PASSWORD y UBW_E2E_MIGRATE=1 (y prepara el bench)',
);

async function login(page: Page) {
  await page.goto('/login');
  await page.getByLabel('Usuario').fill(ADMIN_USER ?? '');
  await page.getByLabel('Contraseña').fill(ADMIN_PASSWORD ?? '');
  await page.getByRole('button', { name: 'Iniciar sesión' }).click();
  await expect(page.getByRole('button', { name: /Menú de usuario/ })).toBeVisible();
}

async function setOwnPermission(page: Page, label: RegExp, value: boolean) {
  await page.goto('/admin/users');
  await page.getByRole('button', { name: `Editar ${ADMIN_USER}` }).click();
  const dialog = page.getByRole('dialog');
  const toggle = dialog.getByRole('switch', { name: label });
  if ((await toggle.isChecked()) !== value) {
    await toggle.click({ force: true });
  }
  await dialog.getByRole('button', { name: 'Guardar' }).click();
  await expect(dialog).toBeHidden();
}

async function createConnection(
  page: Page,
  dbType: 'postgresql' | 'mysql',
  name: string,
  port: string,
  readOnly: boolean,
): Promise<string> {
  await page.goto(`/connections/new?db_type=${dbType}`);
  await page.getByRole('textbox', { name: /^Nombre/ }).fill(name);
  await page.getByRole('textbox', { name: /^host/ }).fill('host.docker.internal');
  await page.getByRole('textbox', { name: /^port/ }).fill(port);
  await page.getByRole('textbox', { name: /^user/ }).fill('bench');
  await page.getByRole('textbox', { name: /^database/ }).fill('bench');
  await page.getByLabel(/^Contraseña/).fill(BENCH_PASSWORD ?? '');
  const readOnlySwitch = page.getByRole('switch', { name: /^Solo lectura/ });
  if ((await readOnlySwitch.isChecked()) !== readOnly) {
    await readOnlySwitch.click({ force: true });
  }
  await page.getByRole('button', { name: 'Crear conexión' }).click();
  await expect(page.getByRole('heading', { name })).toBeVisible();
  return page.url();
}

async function associate(page: Page, connection: string, dbType: string, alias: string) {
  await page.getByRole('tab', { name: 'Conexiones' }).click();
  await page.getByRole('combobox', { name: 'Conexión' }).selectOption({ label: `${connection} (${dbType})` });
  await page.getByRole('textbox', { name: /^Alias/ }).fill(alias);
  await page.getByRole('button', { name: 'Asociar' }).click();
  await expect(page.getByRole('cell', { name: alias, exact: true })).toBeVisible();
}

/** Espera a la ejecución recién lanzada (otra URL que `from`: el plan también vive en /runs/) y a su estado. */
async function waitStatus(page: Page, status: string, from: string) {
  await expect(page).not.toHaveURL(from);
  await expect(page).toHaveURL(/\/runs\//);
  await expect(page.getByText(status, { exact: true }).first()).toBeVisible({ timeout: 120_000 });
}

test('planificar, modo seco y aplicar una migración PostgreSQL → MySQL', async ({ page }) => {
  // Crea tablas en un destino compartido del bench: la copia de --repeat-each chocaría con la primera.
  test.skip(test.info().repeatEachIndex > 0, 'Escribe en un destino compartido');
  test.setTimeout(300_000);
  const stamp = Date.now();
  const [pg, my, project] = [`e2e-mig-pg-${stamp}`, `e2e-mig-my-${stamp}`, `e2e-mig-${stamp}`];
  await login(page);
  await page.goto('/admin/allowlist');
  if (!(await page.getByText('host.docker.internal', { exact: true }).count())) {
    await page.getByRole('textbox', { name: /^Destino/ }).fill('host.docker.internal');
    await page.getByRole('button', { name: 'Añadir destino' }).click();
    await page.reload();
  }
  await setOwnPermission(page, /Puede aplicar DDL/, true);
  const pgUrl = await createConnection(page, 'postgresql', pg, PG_PORT, true);
  const myUrl = await createConnection(page, 'mysql', my, MYSQL_PORT, false);

  await page.goto('/projects');
  await page.getByRole('button', { name: 'Nuevo proyecto' }).click();
  await page
    .getByRole('dialog')
    .getByRole('textbox', { name: /^Nombre/ })
    .fill(project);
  await page.getByRole('dialog').getByRole('button', { name: 'Crear proyecto' }).click();
  await expect(page.getByRole('heading', { name: project })).toBeVisible();
  const projectUrl = page.url();
  await associate(page, pg, 'postgresql', 'origen');
  await associate(page, my, 'mysql', 'destino');

  // Plan.
  await page.getByRole('tab', { name: 'Ejecuciones' }).click();
  await page.getByRole('button', { name: 'Lanzar ejecución' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('combobox', { name: 'Operación' }).selectOption({ label: 'Plan de migración DDL' });
  await dialog.getByRole('combobox', { name: 'Conexión origen' }).selectOption('origen');
  await dialog.getByRole('textbox', { name: /^Schema origen/ }).fill('public');
  await dialog.getByRole('combobox', { name: 'Motor destino' }).selectOption('mysql');
  await dialog.getByRole('button', { name: 'Lanzar' }).click();
  await waitStatus(page, 'Correcta', projectUrl);
  const planUrl = page.url();
  await expect(page.getByText('postgresql (public) → mysql')).toBeVisible();
  await page.getByRole('tab', { name: /^Tablas/ }).click();
  await expect(page.getByRole('button', { name: /ubw_e2e_pedido/ })).toBeVisible();

  // Modo seco.
  await page.getByRole('combobox', { name: 'Conexión destino' }).selectOption('destino');
  await expect(page.getByRole('button', { name: 'Aplicar…' })).toBeDisabled();
  await page.getByRole('button', { name: 'Modo seco' }).click();
  await waitStatus(page, 'Correcta', planUrl);
  await expect(page.getByText('Modo seco correcto', { exact: true })).toBeVisible();

  // Aplicar con doble confirmación.
  await page.goto(planUrl);
  await page.getByRole('combobox', { name: 'Conexión destino' }).selectOption('destino');
  await page.getByRole('button', { name: 'Aplicar…' }).click();
  const confirm = page.getByRole('dialog');
  await confirm.getByRole('checkbox', { name: /Entiendo que no es atómico/ }).check();
  await confirm.getByRole('textbox', { name: 'Escribe «destino» para confirmar' }).fill('destino');
  await confirm.getByRole('button', { name: 'Aplicar ahora' }).click();
  await waitStatus(page, 'Correcta', planUrl);
  await expect(page.getByText(/Sentencias aplicadas: (\d+) de \1\./)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Relanzar' })).toHaveCount(0);

  // Un segundo modo seco detecta que las tablas ya existen.
  await page.goto(planUrl);
  await page.getByRole('combobox', { name: 'Conexión destino' }).selectOption('destino');
  await page.getByRole('button', { name: 'Modo seco' }).click();
  await waitStatus(page, 'Fallida', planUrl);
  await expect(page.getByText('El destino ya tiene objetos del plan')).toBeVisible();

  // Limpieza (las tablas del bench las borra e2e_migrate_fixture teardown).
  await page.goto(projectUrl);
  await page.getByRole('tab', { name: 'Ajustes' }).click();
  await page.getByRole('button', { name: 'Borrar proyecto' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Borrar' }).click();
  for (const url of [pgUrl, myUrl]) {
    await page.goto(url);
    await page.getByRole('button', { name: 'Borrar' }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Borrar' }).click();
    await expect(page.getByRole('heading', { name: 'Conexiones' })).toBeVisible();
  }
  await setOwnPermission(page, /Puede aplicar DDL/, false);
});
