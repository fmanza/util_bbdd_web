"""Datos del E2E de migración (``frontend/e2e/migrate.spec.ts``) en los contenedores bench.

La web no puede crear tablas en el origen (su único camino de escritura es la propia migración), así que el E2E
necesita este paso previo y su limpieza, desde ``backend/`` y con ``UTIL_BBDD_BENCH_PASSWORD``::

    uv run python -m tests.integration.e2e_migrate_fixture setup     # tablas en PostgreSQL; MySQL sin ellas
    uv run python -m tests.integration.e2e_migrate_fixture teardown  # borra las tablas en los dos
"""

from __future__ import annotations

import sys

from tests.integration.test_bench_explorer import _execute

TABLES = ("ubw_e2e_pedido", "ubw_e2e_cliente")  # hijo antes que padre
SOURCE = [
    "CREATE TABLE ubw_e2e_cliente (id INT PRIMARY KEY, nombre VARCHAR(80) NOT NULL, alta DATE)",
    "CREATE TABLE ubw_e2e_pedido (id INT PRIMARY KEY, cliente_id INT REFERENCES ubw_e2e_cliente(id), "
    "total NUMERIC(10, 2))",
]


def _drop(engine: str) -> None:
    for table in TABLES:
        try:
            _execute(engine, [f"DROP TABLE {table}"], ignore_errors=True)
        except Exception:  # noqa: S110 (no existe)
            pass


def main(action: str) -> None:
    _drop("mysql")
    _drop("postgresql")
    if action == "setup":
        _execute("postgresql", SOURCE)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "setup")
