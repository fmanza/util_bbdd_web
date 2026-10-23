import { expect, type Page, test } from './fixtures';

// Requiere el admin E2E (ver login.spec.ts). El flujo contra el bench PostgreSQL necesita además
// UTIL_BBDD_BENCH_PASSWORD y que el contenedor web alcance el host por host.docker.internal.
const ADMIN_USER = process.env.UBW_E2E_ADMIN_USER;
const ADMIN_PASSWORD = process.env.UBW_E2E_ADMIN_PASSWORD;
const BENCH_PASSWORD = process.env.UTIL_BBDD_BENCH_PASSWORD;
const BENCH_PG_PORT = process.env.UTIL_BBDD_BENCH_POSTGRES_PORT ?? '55432';

test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define UBW_E2E_ADMIN_USER y UBW_E2E_ADMIN_PASSWORD');

async function login(page: Page) {
  await page.goto('/login');
  await page.getByLabel('Usuario').fill(ADMIN_USER ?? '');
  await page.getByLabel('Contraseña').fill(ADMIN_PASSWORD ?? '');
  await page.getByRole('button', { name: 'Iniciar sesión' }).click();
  await expect(page.getByRole('button', { name: /Menú de usuario/ })).toBeVisible();
}

async function createPostgres(page: Page, name: string, host: string, port: string, password: string) {
  await page.goto('/connections/new?db_type=postgresql');
  await page.getByRole('textbox', { name: /^Nombre/ }).fill(name);
  await page.getByRole('textbox', { name: /^host/ }).fill(host);
  await page.getByRole('textbox', { name: /^port/ }).fill(port);
  await page.getByRole('textbox', { name: /^user/ }).fill('bench');
  await page.getByRole('textbox', { name: /^database/ }).fill('bench');
  await page.getByLabel(/^Contraseña/).fill(password);
  await page.getByRole('button', { name: 'Crear conexión' }).click();
  await expect(page.getByRole('heading', { name })).toBeVisible();
}

async function deleteCurrentConnection(page: Page, name: string) {
  await page.getByRole('button', { name: 'Borrar' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toContainText(`«${name}»`);
  await dialog.getByRole('button', { name: 'Borrar' }).click();
  await expect(page.getByRole('heading', { name: 'Conexiones' })).toBeVisible();
}

test('el catálogo muestra los motores y la ficha de PostgreSQL', async ({ page }) => {
  await login(page);
  await page.getByRole('link', { name: 'Motores' }).click();

  await expect(page.getByRole('rowheader', { name: 'SQL Server' })).toBeVisible();
  await page.getByRole('link', { name: 'PostgreSQL' }).click();
  await expect(page.getByRole('heading', { name: 'PostgreSQL' })).toBeVisible();
  await expect(page.getByText('sslmode')).toBeVisible();
});

test('una conexión a un destino no permitido no se intenta y se puede borrar', async ({ page }) => {
  const name = `e2e-denegada-${Date.now()}`;
  await login(page);
  // IP literal de documentación (RFC 5737): no depende del DNS y no está en la allowlist.
  await createPostgres(page, name, '203.0.113.10', '5432', 'no-importa-1234');

  await expect(page.getByText('Guardada (cifrada)')).toBeVisible();
  await expect(page.getByText('no-importa-1234')).toHaveCount(0);
  await page.getByRole('button', { name: 'Probar conexión' }).click();
  await expect(page.getByText('La conexión ha fallado')).toBeVisible();
  await expect(page.getByText(/lista de destinos permitidos/)).toBeVisible();

  await deleteCurrentConnection(page, name);
  await expect(page.getByRole('link', { name })).toHaveCount(0);
});

test('el admin añade y quita un destino permitido', async ({ page }) => {
  const pattern = `*.e2e-${Date.now()}.local`;
  await login(page);
  await page.getByRole('link', { name: 'Destinos permitidos' }).click();
  await page.getByRole('textbox', { name: /^Destino/ }).fill(pattern);
  await page.getByRole('button', { name: 'Añadir destino' }).click();
  await expect(page.getByText(pattern)).toBeVisible();

  await page.getByRole('button', { name: `Quitar ${pattern}` }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Quitar' }).click();
  await expect(page.getByText(pattern)).toHaveCount(0);
});

test('prueba y readiness reales contra el bench PostgreSQL', async ({ page }) => {
  test.skip(!BENCH_PASSWORD, 'Define UTIL_BBDD_BENCH_PASSWORD');
  const name = `e2e-bench-${Date.now()}`;
  await login(page);
  // Idempotente y sin limpieza: otra copia del test (--repeat-each, workers en paralelo) puede estar usando la misma
  // entrada; quitarla al final rompería a la otra. En el volumen de desarrollo queda permitida.
  await page.goto('/admin/allowlist');
  if (!(await page.getByText('host.docker.internal', { exact: true }).count())) {
    await page.getByRole('textbox', { name: /^Destino/ }).fill('host.docker.internal');
    await page.getByRole('button', { name: 'Añadir destino' }).click();
    await page.reload(); // tolera el 409 si otra copia la ha creado a la vez
    await expect(page.getByText('host.docker.internal', { exact: true })).toBeVisible();
  }

  await createPostgres(page, name, 'host.docker.internal', BENCH_PG_PORT, BENCH_PASSWORD ?? '');
  await page.getByRole('button', { name: 'Probar conexión' }).click();
  await expect(page.getByText('Conexión correcta')).toBeVisible({ timeout: 30_000 });
  await page.getByRole('button', { name: 'Readiness' }).click();
  await expect(page.getByRole('heading', { name: 'Readiness del motor' })).toBeVisible();
  await expect(page.getByRole('columnheader', { name: 'Recomendación' })).toBeVisible({ timeout: 30_000 });

  await deleteCurrentConnection(page, name);
});
