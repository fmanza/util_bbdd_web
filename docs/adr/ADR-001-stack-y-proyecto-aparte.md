# ADR-001 — Stack tecnológico y proyecto aparte

- **Estado**: Aceptado
- **Fecha**: 2026-10-19

## Contexto

util_bbdd es una librería Python con API pública bajo SemVer, distribuida como wheel. Se quiere una interfaz web
multiusuario en React, en Docker y con la configuración en SQLite.

## Decisión

1. **Proyecto aparte** (`util_bbdd_web`) que consume util_bbdd con versión fijada. La web es una aplicación con su
   propio ciclo de releases, dependencias (Node, FastAPI) y superficie de seguridad; mezclarla con la librería
   ensuciaría SemVer, el CHANGELOG y su CI determinista. Dentro del proyecto, backend y frontend van en
   **monorepo** para evitar la deriva de tipos.
2. **Frontend**: Vite + React + TypeScript estricto (SPA interna detrás de login, sin SEO ni SSR), React Router,
   TanStack Query, **Mantine** como librería de UI (tablas, formularios, modo oscuro sin montar un sistema propio),
   React Hook Form + Zod, i18next. Cliente tipado generado desde OpenAPI (`openapi-typescript` + `openapi-fetch`).
3. **Backend**: FastAPI + Pydantic v2 en Python 3.12 (mismo lenguaje que util_bbdd; OpenAPI automático).
4. **Persistencia**: SQLite con SQLAlchemy 2 + Alembic; PRAGMA `journal_mode=WAL`, `synchronous=NORMAL`,
   `busy_timeout=5000`, `foreign_keys=ON`.
5. **Herramientas**: uv (lock con `exclude-newer`), npm (lockfile, `--before`). Se eligió **npm** frente a pnpm por
   venir con Node y evitar otra herramienta en los equipos; el cambio a pnpm no afecta a la arquitectura.
6. **TypeScript 5.9**: TypeScript 6/7 aún no es compatible con `openapi-typescript` 7.13 ni con `typescript-eslint`
   8.71 (verificado el 2026-10-19).

## Consecuencias

- Una versión MAJOR de util_bbdd solo afecta a la capa anticorrupción (ADR-006).
- SQLite limita a un escritor simultáneo: suficiente para configuración y pocos usuarios; ruta de escape a
  PostgreSQL cambiando la URL de SQLAlchemy.
