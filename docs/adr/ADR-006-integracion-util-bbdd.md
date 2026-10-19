# ADR-006 — Integración con util_bbdd: capa anticorrupción y versión fijada

- **Estado**: Aceptado
- **Fecha**: 2026-10-19

## Contexto

util_bbdd 4.0.0 no está publicado en un índice accesible (el repositorio GitHub responde 404 sin credenciales y el
tag aún no se ha subido). El build de Docker y el CI deben ser reproducibles sin credenciales.

## Decisión

1. **Capa anticorrupción**: solo `backend/app/integrations/util_bbdd/` importa `util_bbdd`. Expone funciones y tipos
   propios; lo verifica `backend/tests/unit/test_architecture.py`.
2. **Wheel vendorizado**: `vendor/wheels/util_bbdd-4.0.0-py3-none-any.whl` (construido por la release de util_bbdd,
   SHA-256 `a9a71aec8bc5659bf93ebc7ae80101068df8564e9c8b5345957cd19acc729f60`), referenciado en
   `[tool.uv.sources]`. Se versiona en git (≈ 0,9 MB).
3. **Extras usados**: `oracle, mariadb, mysql, postgresql, migrate, analysis`; drivers sin extra en util_bbdd
   (`pymssql`, `aiosqlite`, `jaydebeapi`, `pyodbc`) declarados en la web (GAPS G3).
4. **Actualizar util_bbdd**: copiar el wheel nuevo, cambiar versión en `dependencies` y `[tool.uv.sources]`,
   `uv lock`, ejecutar la suite y los tests de contrato de la capa, nota en el CHANGELOG.

## Alternativas descartadas

- `git+https://…@v4.0.0`: requiere credenciales en el build y el tag publicado.
- Ruta local `../util_bbdd`: el build dependería del árbol de trabajo, no de una versión.

## Plan de salida

En la Fase 10, publicar util_bbdd en un índice privado o en GitHub Releases y sustituir el wheel vendorizado.
