import '@testing-library/jest-dom/vitest';
import i18n from '../i18n';
import features from '../i18n/es/features.json';

import { cleanup, configure } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

// En la app las traducciones de las pantallas llegan con la primera ruta lazy; en los tests, desde el principio.
i18n.addResourceBundle('es', 'translation', features, true, true);

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

// Textarea con autosize de Mantine escucha la carga de fuentes; jsdom no implementa document.fonts.
Object.defineProperty(document, 'fonts', {
  configurable: true,
  value: { addEventListener: vi.fn(), removeEventListener: vi.fn(), ready: Promise.resolve() },
});

// Con toda la suite en paralelo (Mantine + lazy routes), 1 s de espera por defecto se queda corto en CI.
configure({ asyncUtilTimeout: 3000 });

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
