import { expect, test as base } from '@playwright/test';

export { expect, type Locator, type Page } from '@playwright/test';

/**
 * `test` con vigilancia de la CSP de la SPA (Fase 10): falla si la página registra una violación de **su** CSP.
 * Los iframes de vistas previas y del sitio HTML tienen una CSP propia más estricta (`default-src 'none'`, ADR-007)
 * y pueden registrar bloqueos esperados del contenido generado (Chromium los atribuye a veces a la página
 * principal): se reconocen por esa directiva o por su URL (`/api/v1/runs/…`).
 */
export const test = base.extend({
  page: async ({ page }, provide) => {
    const violations: string[] = [];
    page.on('console', (message) => {
      const text = message.text();
      const source = message.location().url;
      const sandboxed = source.includes('/api/v1/runs/') || text.includes(`"default-src 'none'"`);
      if (text.includes('Content Security Policy') && !sandboxed) {
        violations.push(`${text} (${source})`);
      }
    });
    await provide(page);
    expect(violations, 'Violaciones de la CSP de la SPA').toEqual([]);
  },
});
