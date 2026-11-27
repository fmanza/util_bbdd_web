---
applyTo: "frontend/**/*.{ts,tsx}"
---
# Frontend (React + TypeScript) — reglas

> **TL;DR** — TypeScript estricto, componentes funcionales, datos solo vía TanStack Query y el cliente OpenAPI
> generado, UI con Mantine, textos en i18n, accesibilidad WCAG 2.2 AA.

## Estructura
- `src/features/<área>/`: páginas, componentes y hooks de una funcionalidad (`useX.ts` con TanStack Query).
- `src/components/`: UI compartida sin lógica de negocio.
- `src/api/`: `client.ts` (único punto con `fetch`) y `schema.d.ts` (generado, no editar).
- Rutas en `src/app/router.tsx`, hijas de `Layout`; páginas de cada fase con `lazy` para dividir el bundle.

## Datos
- `queryKey` estables y jerárquicas (`['projects', projectId, 'runs']`); invalidar tras mutaciones.
- Errores: `ApiError` con *problem details*; mostrar `title`/`detail`, nunca trazas.
- Progreso de ejecuciones por SSE (Fase 3) con *fallback* a `refetchInterval`.

## UI y accesibilidad
- Mantine; tema en `app/theme.ts` (lo aplica `app/Providers.tsx`); modo oscuro automático.
- **Formularios con ayuda y varias columnas** (regla del proyecto): la ayuda (`description`) va **debajo** del campo
  (orden `label → input → description → error`, fijado en el tema; no se cambia con `inputWrapperOrder`). Las filas de
  campos usan `align="flex-start"` (o `alignItems: 'start'` en rejilla) y etiquetas de una línea, así todos los
  campos empiezan a la misma altura. El botón de un formulario en línea va dentro de `components/InlineAction.tsx`,
  nunca con márgenes fijos (`mt={50}`). Lo comprueba `components/formRule.test.tsx`.
- Cada vista con estados de carga, vacío, error y sin permiso.
- Formularios: React Hook Form + Zod; errores asociados al campo; formularios de conexión generados desde los
  `connection_params` del catálogo de motores.
- Acciones destructivas: modal de confirmación que repite el nombre del recurso y muestra el modo seco.
- Vistas previas HTML de artefactos en `iframe` con `sandbox` (sin `allow-scripts` salvo necesidad justificada).

## Estilo
- Sin `any`; tipos del cliente generado; `import type` para tipos.
- Textos con `useTranslation()`; claves en `core.json` (lo que se ve sin pasar por una ruta lazy) o `features.json`
  (pantallas; se carga con la primera ruta lazy), **en `src/i18n/es/` y en `src/i18n/en/`** (inglés británico, términos
  en `.ai/glossary.md`). `i18n.test.ts` exige las mismas claves y marcadores en los dos idiomas, y `literals.test.ts`,
  que ningún texto visible esté escrito en el código.
- Permisos: `can(me, 'permiso')` (`features/auth/useAuth.ts`); las rutas y el menú de *Administración* toman el permiso
  de su entrada en `app/navigation.ts` (ADR-014). Nada compara con un nombre de rol.
- Prettier + ESLint (`npm run lint`) sin avisos.
