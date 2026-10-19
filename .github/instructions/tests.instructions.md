---
applyTo: "backend/tests/**,frontend/src/**/*.test.{ts,tsx},frontend/e2e/**"
---
# Tests — reglas

## Backend (pytest)
- `tests/unit`: lógica sin I/O. `tests/api`: `TestClient` con la fixture `client` (SQLite en `tmp_path`).
  `tests/integration`: `@pytest.mark.integration`, BD reales, fuera del CI.
- Cada endpoint nuevo: caso feliz, validación (422), sin sesión (401), sin permiso / recurso ajeno (404).
- Toda función que maneje secretos: test que verifique que el secreto no aparece en la respuesta ni en el log
  (`caplog`).
- `tests/unit/test_architecture.py` no se relaja: solo la capa anticorrupción importa util_bbdd.

## Frontend (Vitest + Testing Library)
- Renderizar con `renderRoute()` o `renderWithProviders()` de `src/test/render.tsx`.
- Consultas por rol y texto accesible; nada de `querySelector` ni `data-testid` salvo último recurso.
- `fetch` sustituido con `vi.stubGlobal('fetch', ...)`; cubrir carga, éxito, error y vacío.

## E2E (Playwright)
- Contra `docker compose up` (`UBW_E2E_URL`); un fichero por flujo de usuario de la fase.
- Datos de prueba creados por la propia prueba vía API; sin dependencias entre tests.
