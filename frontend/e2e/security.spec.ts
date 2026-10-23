import { expect, type Page, test } from './fixtures';

// Endurecimiento (Fase 10): cabeceras, cookies `__Host-` y bloqueo de cuenta con su rastro en la auditoría.
// El bloqueo hace 5 inicios de sesión fallidos desde la misma IP: con varias ejecuciones seguidas de la suite, sube
// UBW_RATE_LIMIT_LOGIN_FAILURES en el compose (o reinicia `web`) para no llegar al límite por IP.
const ADMIN_USER = process.env.UBW_E2E_ADMIN_USER;
const ADMIN_PASSWORD = process.env.UBW_E2E_ADMIN_PASSWORD;

async function login(page: Page, username: string, password: string) {
  await page.goto('/login');
  await page.getByLabel('Usuario').fill(username);
  await page.getByLabel('Contraseña').fill(password);
  await page.getByRole('button', { name: 'Iniciar sesión' }).click();
}

async function loginOk(page: Page, username: string, password: string) {
  await login(page, username, password);
  await expect(page.getByRole('button', { name: /Menú de usuario/ })).toBeVisible();
}

test('la SPA y la API llevan cabeceras de seguridad y request_id', async ({ request }) => {
  const spa = await request.get('/projects');
  const csp = spa.headers()['content-security-policy'] ?? '';
  expect(csp).toContain("script-src 'self';");
  expect(csp).toContain("frame-ancestors 'none'");
  expect(spa.headers()['x-content-type-options']).toBe('nosniff');
  expect(spa.headers()['server']).toBeUndefined();

  const api = await request.get('/api/health', { headers: { 'X-Request-ID': 'e2e-request-0001' } });
  expect(api.headers()['x-request-id']).toBe('e2e-request-0001');
  expect(api.headers()['cache-control']).toBe('no-store');
  expect((await request.get('/api/openapi.json')).status()).toBe(404);
  // Sin token configurado, 404; con `ubw_metrics_token`, 401 sin el Bearer: nunca abierto.
  expect([401, 404]).toContain((await request.get('/metrics')).status());
});

test.describe('con el admin E2E', () => {
  test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define UBW_E2E_ADMIN_USER y UBW_E2E_ADMIN_PASSWORD');

  test('las cookies de sesión usan el prefijo __Host-', async ({ page, context }) => {
    await loginOk(page, ADMIN_USER ?? '', ADMIN_PASSWORD ?? '');
    const cookies = await context.cookies();
    const session = cookies.find((cookie) => cookie.name === '__Host-ubw_session');
    expect(session?.secure).toBe(true);
    expect(session?.httpOnly).toBe(true);
    expect(session?.path).toBe('/');
    expect(cookies.find((cookie) => cookie.name === '__Host-ubw_csrf')?.httpOnly).toBe(false);
  });

  test('cinco fallos bloquean la cuenta y queda en la auditoría', async ({ page, browser }) => {
    test.skip(test.info().repeatEachIndex > 0, 'Gasta intentos fallidos del límite por IP');
    const username = `e2e-bloqueo-${Date.now()}`;
    const password = 'frase-de-paso-bloqueo-1234';
    await loginOk(page, ADMIN_USER ?? '', ADMIN_PASSWORD ?? '');
    await page.goto('/admin/users');
    await page.getByRole('button', { name: 'Nuevo usuario' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('textbox', { name: /^Usuario/ }).fill(username);
    await dialog.getByRole('textbox', { name: /Nombre visible/ }).fill('Bloqueo E2E');
    await dialog.getByLabel(/^Contraseña/).fill(password);
    await dialog.getByRole('button', { name: 'Crear usuario' }).click();
    await expect(dialog).toBeHidden();
    await page.getByRole('textbox', { name: 'Buscar por usuario o nombre' }).fill(username);
    await expect(page.getByRole('cell', { name: username, exact: true })).toBeVisible();

    const other = await browser.newPage();
    for (let attempt = 0; attempt < 5; attempt += 1) {
      await login(other, username, 'contraseña-equivocada');
      await expect(other.getByRole('alert')).toContainText('Credenciales no válidas');
    }
    // Con la contraseña buena sigue rechazado, con el mismo mensaje (sin revelar el bloqueo).
    await login(other, username, password);
    await expect(other.getByRole('alert')).toContainText('Credenciales no válidas');
    await other.close();

    await page.goto('/admin/audit');
    await expect(page.getByRole('cell', { name: 'Bloqueo de cuenta' }).first()).toBeVisible();
  });
});
