// Tema del primer fotograma (1.21.0), antes de que arranque React: copia local del tema de la cuenta.
// Script clásico servido desde 'self' (lo admite la CSP de la SPA, sin hash ni 'unsafe-inline'). La clave es
// COLOR_SCHEME_STORAGE_KEY de src/app/colorScheme.ts; un test vigila que coincidan.
(function () {
  var KEY = 'ubw-color-scheme';
  var scheme = 'auto';
  try {
    var stored = window.localStorage.getItem(KEY);
    if (stored === 'light' || stored === 'dark' || stored === 'auto') scheme = stored;
  } catch (e) {
    // localStorage inaccesible (privacidad, cuota): se usa el del sistema.
  }
  if (scheme === 'auto') {
    try {
      scheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    } catch (e) {
      scheme = 'light';
    }
  }
  document.documentElement.setAttribute('data-mantine-color-scheme', scheme);
})();
