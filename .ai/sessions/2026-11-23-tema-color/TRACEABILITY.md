# TRACEABILITY

## Session metadata
- id: 2026-11-23-tema-color
- fecha: 2026-11-23
- rama: develop
- skill: new_feature + audit_code + version_closure
- fase: PLAN v2 (externo) → revisión (NO_GO: la 0012 en modo batch borraría datos) → PLAN v3 + AUDIT_PLAN v3
  (GO_CONDICIONAL, aprobado) + IMPLEMENT + AUDIT_CODE (APROBADO CON CONDICIONES; M1–M3 corregidos) + VERSION → 1.21.0

## Prompt issued
«Revisa el PLAN y AUDIT_PLAN» (PLAN v2 del tema claro/oscuro/sistema guardado en la cuenta) → «Aplica las
correcciones al PLAN y genera la v3» → «Aprobado, guarda la sesión y pasa a IMPLEMENT».

## Context supplied
- Web 1.20.0; Mantine 9.6.3 (`defaultColorScheme="auto"`, sin gestor propio); SPA_CSP `script-src 'self'` + hash del
  puente; `PRAGMA foreign_keys=ON` también en las migraciones (`alembic/env.py` usa el engine de la app).
- PLAN v3 completo en [PLAN.md](PLAN.md).

## AI output summary
- Revisión del PLAN v2: `batch_alter_table` + `CheckConstraint` recrea `users` y, con `foreign_keys=ON`, el
  `DROP TABLE users` dispara los `ON DELETE` (reproducido con sqlite3: sesiones borradas, auditoría sin autor).
  Otros hallazgos: contradicción en la regla del hook, carrera en el optimista, `Menu` se cierra al elegir, clave de
  `localStorage` interna de Mantine.
- Backend: `ColorScheme` (modelos y esquemas), `User.color_scheme` + `ck_users_color_scheme`, `Me.color_scheme`,
  `PreferencesUpdate` (`extra="forbid"`), `users.update_preferences` (sin auditoría), `PATCH /auth/me/preferences`.
  Migración `0012_user_color_scheme.py` con `ALTER TABLE ADD COLUMN ... CHECK` / `DROP COLUMN` (verificado en
  SQLite 3.50.4).
- Frontend: `app/colorScheme.ts` (clave `ubw-color-scheme`, gestor, `useResolvedColorScheme`), `public/color-scheme.js`
  en el `<head>`, `useUpdatePreferences` (optimista con reversión), `useColorSchemeSync` (regla del `ref`, en
  `Layout`), apartado «Tema» en `UserMenu` (`menuitemradio` vía ref, `closeMenuOnClick={false}`, desactivado mientras
  guarda, alerta en el menú), `frameTheme.ts` (paletas AA), `buildFrameDocument(..., scheme)`, `ArtifactBrowser` y
  `MarkdownViewer` con el tema en las dependencias, `mermaid.ts` con tema y cola de módulo. i18n `theme.*`.
- Desviaciones del PLAN v3:
  - Fixtures de `me` en `src/test/api.ts` (no `fixtures.ts`).
  - El enlace claro del iframe pasa de `#1c7ed6` (4.20:1) a `#1864ab`: el «claro actual» no cumplía AA.
  - `ArtifactBrowser` reutiliza `frameBaseStyle` en lugar de su `MARKDOWN_STYLE` duplicado.
  - Sin referencia de la API que listar: no existe un documento con los endpoints de auth.
- Tests: backend `test_backup.py` (revisión de cabeza 0012), `test_auth.py` (+7) y `test_migration_0012_preserves_related_rows`; frontend `auth.test.tsx`
  (+5), `colorScheme.test.ts`, `frameTheme.test.ts`, `mermaid.test.ts` (+3), `markdownNav.test.ts` (+1).
- Comprobación de los tests: con la 0012 en modo batch, el test de migración falla con `([], [None], [], [])`; con
  `closeMenuOnClick={true}`, fallan dos tests del menú.
- Docs: CHANGELOG `[Unreleased]`, `usuarios_y_sesiones.md` (apartado «Tema claro u oscuro»), `guia_usuario.md`.
- AUDIT_CODE (propio, foco «todo»): APROBADO CON CONDICIONES. Corregidos en `UserMenu.tsx`:
  - M1: `onClose` solo llama a `preferences.reset()` sin guardado en curso (`MutationObserver.reset()` desengancha la
    mutación y reactivaba las opciones con la petición viva).
  - M2: sin la guarda `if (!checked)`: en otra pestaña la marca (caché de `me`, sin refresco al enfocar) puede no
    coincidir con el tema sincronizado por `storage`; el PATCH es idempotente.
  - M3: `aria-disabled` + `data-disabled` en lugar de `disabled` mientras se guarda (el foco no se pierde, WCAG 2.4.3);
    el clic se ignora en el `onClick`.
  - Tests: «desactivadas sin perder el foco y no envían nada», «cerrar y reabrir … no reactiva las opciones» y «la
    opción marcada se puede volver a elegir si otra pestaña cambió el tema»; deshaciendo cada corrección falla su test.
  - Pendientes menores (corregidos después de 1.21.0, ver Evidencias): m4 `role="alert"` dentro de `role="menu"` (hipótesis axe), m5
    `ArtifactBrowser` no guarda el tema junto al HTML (doble recarga), m6 `id` fijo del rótulo (mejor `useId`), y un
    test de regeneración de la vista previa al cambiar de tema.

## Evidencias
- Backend: ruff format/check, mypy y `export_openapi --check` en verde; `test_auth.py` + `test_cli_and_migrations.py`
  35 passed. Suite completa: 830 passed, 101 skipped, 1 failed (`test_backup_and_restore_round_trip` fijaba la
  revisión de cabeza `0011`; actualizado a `0012`, `test_backup.py` 7 passed).
- Frontend: format, lint, typecheck y build en verde; `dist/color-scheme.js` existe y va antes del módulo en
  `dist/index.html`; `gen:api` estable.
- Frontend tests (`--maxWorkers=4`): 242/245; los 3 fallos son tiempos agotados de 5 s en `runs`, `markdown` y
  `tableFilter`. Con todos los workers, el código **original** da 44 fallos de tiempo en esta máquina, y aislado
  `runs.test.tsx` falla también en el original. Las duraciones alternando original y cambios son equivalentes.
- Tras las correcciones de AUDIT_CODE: format, lint, typecheck y build en verde; frontend (`--maxWorkers=4`)
  247/247 y 34/34 archivos.
- VERSION 1.21.0: versión sincronizada (CHANGELOG, `pyproject.toml`, `app/__init__.py`, `package*.json`, `uv.lock`,
  `openapi.json` `info.version`, `.env.example` `UBW_TAG`) y `.ai/product.md`; `export_openapi --check` en verde.
- Docker: `UBW_TAG=1.21.0 docker compose build` correcto; la imagen trae SQLite 3.40.1 (≥ 3.35, `DROP COLUMN` del
  downgrade de la 0012), `app.__version__` 1.21.0 y `/app/static/color-scheme.js`. En la imagen `backend-dev`:
  `test_cli_and_migrations.py`, `test_auth.py` y `test_backup.py` 42 passed.
- Compose (tras los commits `919cb72` y `985857f`): entorno local limpio (sin `.env` ni volumen `data`), secretos
  creados con `scripts/generate_secrets.py`; `UBW_TAG=1.21.0 UBW_PORT=8081 docker compose up -d` (el 8080 lo ocupa
  otro proyecto). `web` *healthy* y `worker` en marcha; el arranque aplica `0011 -> 0012`. `GET /api/health` 200:
  `version 1.21.0`, `util_bbdd_version 5.9.0`, `database ok`, `worker ok`. `GET /color-scheme.js` 200
  (`text/javascript`), cargado antes del módulo en `index.html`, y la CSP de la SPA sin cambios
  (`script-src 'self' 'sha256-4eVjDELX…'`).
- `zensical build --strict` sin avisos.
- Pendientes m4–m6 (tras 1.21.0, CHANGELOG `[Unreleased]`):
  - m4: el aviso visible del menú ya no lleva rol (describe el grupo con `aria-describedby`) y el anuncio sale de un
    `VisuallyHidden role="alert"` fuera del `Menu`; el test comprueba que no hay `alert` dentro del `menu`.
  - m5: `MarkdownPreview` (exportado) guarda `{ scheme, html }`; nuevo `markdownPreview.test.tsx` (Mermaid simulado
    que marca el tema) exige un único cambio de `srcdoc`; con `frameBaseStyle(scheme)` falla (2 cambios).
  - m6: `useId` para el rótulo y el aviso del grupo *Tema*.
  - Frontend: format, lint, typecheck y build en verde; `auth.test.tsx` + `markdownPreview.test.tsx` 17 passed.
    Suite (`--maxWorkers=4`) 247/248: el fallo es el tiempo agotado conocido de `runs.test.tsx`, que aislado da 8/8.
  - Commit `29f35b6`; CI de `develop` en verde (backend, frontend, docs, image).
- Revisión de la documentación (API y web): descripciones del PATCH y de `PreferencesUpdate` en el OpenAPI
  (`export_openapi` + `gen:api`; solo cambian descripciones), enmienda 1.21.0 de ADR-007, `architecture.md` (tema y
  `public/color-scheme.js`), `documentacion.md`, `proyectos_y_ejecuciones.md` y `usuarios_y_sesiones.md`.
  `export_openapi --check`, `test_auth.py` (30 passed), typecheck, format y `zensical build --strict` en verde.

## Directrices para Futuras IAs
- **[migraciones]**: en SQLite, `batch_alter_table` que recrea una tabla referenciada (`users`) borra en cascada sus
  hijas porque `alembic/env.py` usa el engine con `PRAGMA foreign_keys=ON`. Se usa `ALTER TABLE ADD COLUMN` (admite
  `CHECK` con nombre) y `DROP COLUMN` nativos; el test debe sembrar filas hijas antes de migrar.
- **[migraciones]**: la imagen `python:3.12.14-slim-bookworm` trae SQLite 3.40.1: admite `ALTER TABLE DROP COLUMN`
  (≥ 3.35) y `ADD COLUMN` con `CHECK` con nombre.
- **[migraciones]**: las 0005, 0006, 0007 y 0010 añaden y quitan sus columnas de `users` con `op.add_column` y
  `ALTER TABLE … DROP COLUMN` nativos (antes en modo batch: el `upgrade` de la 0005-0007, con `server_default` de
  expresión, y los cuatro `downgrade` recreaban `users`). `test_downgrade_to_0004_preserves_related_rows` siembra
  filas en la cabecera, baja a la 0004 y vuelve a subir.
- **[frontend]**: el tema vive en `localStorage['ubw-color-scheme']` (`COLOR_SCHEME_STORAGE_KEY`); `public/color-scheme.js`
  repite la clave y `colorScheme.test.ts` vigila que coincidan.
- **[frontend]**: lo que se dibuja dentro de un iframe de Markdown usa `useResolvedColorScheme()` en sus dependencias
  y los colores de `frameTheme.ts` (contraste AA comprobado en `frameTheme.test.ts`); `BRIDGE_SCRIPT` no cambia.
- **[tests]**: en jsdom el desplegable de Mantine `Menu` vuelve a `display: none` tras su transición y solo es
  visible un instante; los tests del menú esperan al elemento montado y consultan con `hidden: true`. El test de
  logout ya existente depende de ese instante y es inestable con carga.
