import '@testing-library/jest-dom/vitest';
import '../i18n';

import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

// jsdom no implementa matchMedia ni ResizeObserver, que Mantine usa.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver = ResizeObserverStub;

// Combobox de Mantine (Select) desplaza la opción activa; jsdom no implementa scrollIntoView.
Element.prototype.scrollIntoView = vi.fn();

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
