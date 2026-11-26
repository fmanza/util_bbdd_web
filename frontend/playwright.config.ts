import { defineConfig, devices } from '@playwright/test';

// E2E contra la aplicación ya levantada (docker compose up). URL configurable con UBW_E2E_URL.
// Primera vez: npx playwright install chromium
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.UBW_E2E_URL ?? 'http://127.0.0.1:8080',
    // Los specs buscan los textos en español; sin sesión, la SPA usa el idioma del navegador (2.0.0).
    locale: 'es-ES',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
