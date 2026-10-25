import { readFile } from 'node:fs/promises';

import { expect, type Page, test } from './fixtures';

// Plantillas de documento (ADR-011). Mismos requisitos que documentation.spec.ts: admin E2E, `e2e-tienda.db` copiada
// al contenedor y UBW_E2E_SQLITE=1. Las plantillas que se suben son las plantillas base de la propia aplicación.
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

/** Plantilla base descargada con el enlace de la pantalla (la cookie de sesión es `Secure`: solo la manda el navegador). */
async function baseTemplate(page: Page, link: 'Word base' | 'Excel base'): Promise<Buffer> {
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('link', { name: link }).click(),
  ]);
  return readFile(await download.path());
}

/** GET de la API desde la página (con la sesión del navegador). */
async function apiJson<T>(page: Page, url: string): Promise<T> {
  return page.evaluate(async (target) => {
    const response = await fetch(target);
    if (!response.ok) throw new Error(`${target}: ${response.status}`);
    return (await response.json()) as T;
  }, url);
}

/** Sube una plantilla desde el formulario visible (pestaña del proyecto o página de admin). */
async function upload(page: Page, name: string, filename: string, buffer: Buffer) {
  const form = page.getByRole('heading', { name: 'Subir plantilla' }).locator('xpath=..');
  await form
    .locator('input[type="file"]')
    .setInputFiles({ name: filename, mimeType: 'application/octet-stream', buffer });
  await form.getByRole('textbox', { name: /^Nombre/ }).fill(name);
  await form.getByRole('button', { name: 'Subir' }).click();
  await expect(page.getByRole('table', { name: 'Plantillas de documento' }).getByText(name)).toBeVisible();
}

test('documentar con una plantilla Word del proyecto y una Excel global', async ({ page }) => {
  test.setTimeout(240_000);
  const stamp = Date.now();
  const connection = `e2e-tpl-${stamp}`;
  const project = `e2e-tpl-${stamp}`;
  const wordName = `Word ${stamp}`;
  const excelName = `Excel ${stamp}`;
  await login(page);

  // Plantilla Excel global, desde Administración.
  await page.goto('/admin/templates');
  await expect(page.getByRole('heading', { name: 'Plantillas de documento' })).toBeVisible();
  await upload(page, excelName, 'marca.xltx', await baseTemplate(page, 'Excel base'));

  // Conexión SQLite y proyecto con alias `tienda`.
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

  // Plantilla Word del proyecto; la global se ve en la pestaña sin poder borrarla.
  await page.getByRole('tab', { name: 'Plantillas' }).click();
  await upload(page, wordName, 'corporativa.docx', await baseTemplate(page, 'Word base'));
  const table = page.getByRole('table', { name: 'Plantillas de documento' });
  await expect(table.getByText(excelName)).toBeVisible();
  await expect(table.getByRole('button', { name: `Borrar ${excelName}` })).toHaveCount(0);

  // Lanzar la documentación con las dos plantillas.
  await page.getByRole('tab', { name: 'Ejecuciones' }).click();
  await page.getByRole('button', { name: 'Lanzar ejecución' }).click();
  const dialog = page.getByRole('dialog');
  await dialog
    .getByRole('combobox', { name: 'Operación' })
    .selectOption({ label: 'Documentación de la base de datos' });
  await dialog.getByRole('combobox', { name: 'Conexión' }).selectOption('tienda');
  await dialog.getByRole('combobox', { name: 'Plantilla Word' }).selectOption({ label: wordName });
  await dialog.getByRole('combobox', { name: 'Plantilla Excel' }).selectOption({ label: excelName });
  await dialog.getByRole('button', { name: 'Lanzar' }).click();
  await expect(page).toHaveURL(/\/runs\//);
  await expect(page.getByText('Correcta')).toBeVisible({ timeout: 120_000 });
  await expect(page.getByText('La ejecución terminó con avisos')).toHaveCount(0);

  // Descarga del Word y registro de las plantillas aplicadas en run.json.
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('link', { name: /Descargar .*\.docx/ }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.docx$/);
  const runId = page.url().split('/runs/')[1] ?? '';
  const detail = await apiJson<{ warnings: string[]; artifacts: { id: number; path: string }[] }>(
    page,
    `/api/v1/runs/${runId}`,
  );
  expect(detail.warnings).toEqual([]);
  const manifestId = detail.artifacts.find((a) => a.path === 'run.json')?.id;
  const manifest = await apiJson<{
    templates: { kind: string; scope: string; name: string; applied: boolean }[];
  }>(page, `/api/v1/runs/${runId}/artifacts/${manifestId}`);
  expect(manifest.templates.map((t) => [t.kind, t.scope, t.name, t.applied])).toEqual([
    ['word', 'project', wordName, true],
    ['excel', 'global', excelName, true],
  ]);

  // Limpieza: proyecto (con su plantilla), conexión y plantilla global.
  await page.goto(projectUrl);
  await page.getByRole('tab', { name: 'Ajustes' }).click();
  await page.getByRole('button', { name: 'Borrar proyecto' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Borrar' }).click();
  await page.goto(connectionUrl);
  await page.getByRole('button', { name: 'Borrar' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Borrar' }).click();
  await expect(page.getByRole('heading', { name: 'Conexiones' })).toBeVisible();
  await page.goto('/admin/templates');
  await page.getByRole('button', { name: `Borrar ${excelName}` }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Borrar' }).click();
  await expect(page.getByText(excelName)).toHaveCount(0);
});
