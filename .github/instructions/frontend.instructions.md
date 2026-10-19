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
- Mantine; tema en `app/Providers.tsx`; modo oscuro automático.
- Cada vista con estados de carga, vacío, error y sin permiso.
- Formularios: React Hook Form + Zod; errores asociados al campo; formularios de conexión generados desde los
  `connection_params` del catálogo de motores.
- Acciones destructivas: modal de confirmación que repite el nombre del recurso y muestra el modo seco.
- Vistas previas HTML de artefactos en `iframe` con `sandbox` (sin `allow-scripts` salvo necesidad justificada).

## Estilo
- Sin `any`; tipos del cliente generado; `import type` para tipos.
- Textos con `useTranslation()`; claves en `src/i18n/es.json`.
- Prettier + ESLint (`npm run lint`) sin avisos.
