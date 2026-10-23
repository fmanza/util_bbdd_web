# ADR-006 — Integración con util_bbdd: capa anticorrupción y versión fijada

- **Estado**: Aceptado (punto 2 revisado en la Fase 10: wheel de GitHub Releases)
- **Fecha**: 2026-10-19 (revisión: 2026-10-23)

## Contexto

util_bbdd 4.0.0 no está publicado en un índice accesible (el repositorio GitHub responde 404 sin credenciales y el
tag aún no se ha subido). El build de Docker y el CI deben ser reproducibles sin credenciales.

## Decisión

1. **Capa anticorrupción**: solo `backend/app/integrations/util_bbdd/` importa `util_bbdd`. Expone funciones y tipos
   propios; lo verifica `backend/tests/unit/test_architecture.py`.
2. **Wheel de la release** (desde la Fase 10): `[tool.uv.sources]` apunta a
   `https://github.com/fmanza/util_bbdd/releases/download/v4.0.0/util_bbdd-4.0.0-py3-none-any.whl` y `uv.lock`
   fija su SHA-256 `a9a71aec8bc5659bf93ebc7ae80101068df8564e9c8b5345957cd19acc729f60` (el mismo fichero que estuvo
   vendorizado en `vendor/wheels/` hasta la 0.10.0; la release lleva también `…whl.sha256`). `uv sync --frozen`
   rechaza un wheel con otro hash (verificado). El build y el CI lo descargan sin credenciales: el repositorio es
   público.
3. **Extras usados**: `oracle, mariadb, mysql, postgresql, migrate, analysis`; drivers sin extra en util_bbdd
   (`pymssql`, `aiosqlite`, `jaydebeapi`, `pyodbc`) declarados en la web (GAPS G3).
4. **Actualizar util_bbdd**: comprobar que la release tiene el wheel (si no, subirlo con `gh release upload`),
   cambiar versión en `dependencies` y la URL en `[tool.uv.sources]`, `uv lock`, ejecutar la suite y los tests de
   contrato de la capa, nota en el CHANGELOG.

## Alternativas descartadas

- `git+https://…@v4.0.0`: en 2026-10 requería credenciales; ahora el repositorio es público, pero obligaría a
  construir la librería en cada build (backend de build y `git` en la imagen) en vez de instalar el wheel de la
  release.
- Ruta local `../util_bbdd`: el build dependería del árbol de trabajo, no de una versión.

## Plan de salida

Hecho en la Fase 10: wheel publicado en la release `v4.0.0` y `vendor/` retirado. Si util_bbdd se publica en un
índice (PyPI o privado), bastará con quitar la entrada de `[tool.uv.sources]`.
