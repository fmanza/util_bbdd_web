---
applyTo: "backend/**/*.py"
---
# Backend (FastAPI + SQLAlchemy) — reglas

> **TL;DR** — Python 3.12, `mypy --strict`, ruff. Routers finos → servicios de dominio → integraciones. Pydantic en
> todo lo que cruza HTTP. util_bbdd solo desde `app/integrations/util_bbdd/`. Operaciones pesadas como jobs.

## Capas y dependencias
- `api/` (routers) → `domain/` (servicios, reglas) → `db/` (modelos, sesión) e `integrations/` (util_bbdd).
- `domain/` no importa FastAPI. `integrations/util_bbdd/` no importa `api/`.
- Dependencias con `Depends` (sesión de BD, usuario actual, ajustes); nada de singletons globales mutables.

## Routers
- Prefijo `/api/v1/<recurso-plural>`; `response_model` siempre; `summary` en español.
- Errores con `HTTPException` o excepciones de dominio mapeadas a *problem details* (`app/core/errors.py`).
- Endpoints que tardan más de ~1 s o tocan una BD destino de forma masiva → encolan un job y devuelven `202` con el
  recurso `run`.

## Persistencia
- SQLAlchemy 2 estilo 2.0 (`select()`, `Mapped[...]`), modelos en `app/db/`.
- Toda alteración de esquema con revisión Alembic (`render_as_batch` para SQLite); `downgrade` implementado.
- Transacciones cortas: SQLite admite un único escritor (WAL + `busy_timeout`).

## util_bbdd
- Firma verificada antes de usarla. Adaptadores que devuelven tipos propios (dataclasses/Pydantic), no objetos de
  util_bbdd.
- `DatabaseDocumentation`: siempre `fichero_salida` explícito y `batch_window_seconds=0`.
- `SchemaComparator.compare()` recibe `Inspector` (`sqlalchemy.inspect(manager.get_sqlalchemy_engine())`).
- `MigrationPlanner`: origen/destino ∈ {oracle, mariadb, mysql, sqlserver, postgresql}, distintos.
- Cerrar siempre los managers (`with` o `close()` en `finally`).

## Estilo
- f-strings; `logging` con `extra={...}` (nunca `print`); `pathlib.Path`; docstrings Google en español.
- Excepciones específicas; `except Exception` solo en bordes (handler global, job runner) y con log.
