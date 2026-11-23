# PLAN (v3) — Tema claro, oscuro o del sistema, guardado en la cuenta

Aprobado el 2026-11-23. Sustituye a la v2: migración 0012 sin recrear `users` (con `foreign_keys=ON` el
`DROP TABLE users` del modo batch dispara los `ON DELETE` de las 10 FK), test de migración con datos relacionados,
regla única de sincronización, sin carrera en el optimista, menú abierto al elegir, clave de `localStorage` propia.

## Datos de entrada

| Dato | Valor |
|---|---|
| Objetivo | Cada usuario elige Claro, Oscuro o Sistema; se guarda en su cuenta y le acompaña en cualquier navegador. Sin destello al cargar; vistas previas Markdown y Mermaid siguen el tema |
| Contrato HTTP | `Me.color_scheme` (nuevo) y `PATCH /api/v1/auth/me/preferences` (nuevo) |
| Pantallas | Menú de usuario de la cabecera |
| Permisos | Cualquier usuario con sesión, solo sobre su cuenta |
| util_bbdd | No se usa |
| Restricciones | Sin dependencias nuevas. Migración 0012 sin recrear `users`. Sin cambios en CSP ni `BRIDGE_SCRIPT` |

## Contrato HTTP

- `ColorScheme = Literal["light", "dark", "auto"]`.
- `Me` añade `color_scheme: ColorScheme` (afecta a `GET /auth/me` y `POST /auth/login`; campo nuevo, no rompe).
- `PATCH /api/v1/auth/me/preferences`: cuerpo `PreferencesUpdate { color_scheme }` con `extra="forbid"`; 200 → `Me`;
  401 / 403 (CSRF) / 422 en problem details. Sin `user_id` en la ruta: siempre `session.user`.
- `UserOut` no expone la preferencia.

## Datos

- Modelo `User`: `color_scheme: Mapped[str] = mapped_column(String(8), default="auto", server_default="auto")` y
  `CheckConstraint("color_scheme IN ('light', 'dark', 'auto')", name="color_scheme")` → `ck_users_color_scheme`.
- `0012_user_color_scheme.py`:
  - upgrade: `ALTER TABLE users ADD COLUMN color_scheme VARCHAR(8) NOT NULL DEFAULT 'auto' CONSTRAINT
    ck_users_color_scheme CHECK (...)`.
  - downgrade: `ALTER TABLE users DROP COLUMN color_scheme` (SQLite ≥ 3.35).
  - Prohibido `batch_alter_table` / `create_check_constraint`: recrean `users`.
  - Verificado en SQLite 3.50.4: rellena `'auto'`, el CHECK rechaza valores y `DROP COLUMN` conserva las hijas.

## Archivos

Backend: `app/api/v1/schemas.py`, `app/domain/identity/users.py` (`update_preferences`, sin auditoría),
`app/api/v1/auth.py` (`PATCH /me/preferences`), `openapi/openapi.json`, `frontend/src/api/schema.d.ts`.

Frontend — selector y sincronización:

- `app/colorScheme.ts` (nuevo): `COLOR_SCHEME_STORAGE_KEY = 'ubw-color-scheme'`; `Providers.tsx` usa
  `localStorageColorSchemeManager({ key })`.
- `useAuth.ts`: `useUpdatePreferences()` optimista (onMutate aplica tema + caché; onError revierte; onSuccess guarda
  el `Me` del servidor). Opciones desactivadas mientras `isPending`.
- `useColorSchemeSync.ts` (nuevo, desde `Layout.tsx`): `ref` con el último valor de cuenta aplicado; si
  `me.color_scheme !== ref` → actualiza `ref` y, si difiere de `useMantineColorScheme().colorScheme`, lo aplica.
  `me === null` → vacía el `ref` sin tocar el tema.
- `UserMenu.tsx`: apartado «Tema», tres `menuitemradio` con `aria-checked`, iconos decorativos,
  `closeMenuOnClick={false}`, alerta `role="alert"` dentro del menú si falla.
- i18n: `theme.label`, `theme.light`, `theme.dark`, `theme.auto`, `theme.saveFailed`.

Frontend — sin destello: `public/color-scheme.js` (script clásico en el `<head>`): lee la clave con `try/catch`,
resuelve `auto` con `matchMedia` y pone `data-mantine-color-scheme` en `<html>`.

Frontend — vistas previas: `frameTheme.ts` (paletas clara/oscura AA), `buildFrameDocument(..., scheme)`,
`MarkdownViewer`/`ArtifactBrowser` con `useComputedColorScheme` en las dependencias, `mermaid.ts` con tema por
`scheme` y cola de módulo.

Documentación: CHANGELOG 1.21.0, guía de usuario, referencia de la API.

## Pruebas

- Backend: `/me` → `'auto'`; PATCH 200 visible en `/me` y login; 422 (valor / campo extra), 403, 401; no afecta a
  otro usuario. `test_migration_0012_preserves_related_rows` (sesión, auditoría, proyecto sobreviven a upgrade y
  downgrade; CHECK rechaza valores). `export_openapi --check`.
- Frontend: selector (PATCH con CSRF, tema, marca, menú abierto), reversión con alerta, desactivado mientras guarda,
  la cuenta manda al cargar, cambio de usuario; `color-scheme.test.ts`, `frameTheme.test.ts` (AA),
  `markdownNav.test.ts` (hash intacto), `mermaid.test.ts` (tema y cola). Build con `dist/color-scheme.js`.

## AUDIT_PLAN (v3) — GO_CONDICIONAL

1. La 0012 no usa batch ni recrea `users`; test con datos relacionados en upgrade y downgrade; CHECK activo.
2. `BRIDGE_SCRIPT` y CSP sin cambios; el test del hash no cambia.
3. Contraste AA en los dos temas.
4. Tema resuelto en las dependencias de la vista previa y de Mermaid; Mermaid en serie.
5. `dist/color-scheme.js` existe; script y `Providers.tsx` comparten la clave.
6. `export_openapi --check` sin diferencias, `schema.d.ts` regenerado.
7. El PATCH no admite identificador de usuario.
8. Hook de sincronización con la regla del `ref`.
9. `closeMenuOnClick={false}`, opciones desactivadas mientras guarda; resolver `menuitemradio` en `Menu.Item`.

Fuera de alcance: el `downgrade` de la 0010 (`batch.drop_column`) recrea `users` con el mismo riesgo.
