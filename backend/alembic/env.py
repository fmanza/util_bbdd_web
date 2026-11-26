"""Entorno de Alembic: usa el engine de la aplicación (con sus PRAGMA) y ``render_as_batch`` para SQLite."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context

import app.db.models  # noqa: F401  (registra los modelos en Base.metadata)
from app.db.base import Base
from app.db.session import get_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=str(get_engine().url),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Migra con ``foreign_keys=OFF``: recrear una tabla (``DROP TABLE`` + ``RENAME``) no debe borrar en cascada ni
    poner a ``NULL`` las filas que apuntan a ella. SQLite ignora el PRAGMA dentro de una transacción, así que se fija
    antes de abrirla; al final ``foreign_key_check`` debe salir vacío (si no, se deshace todo) y la conexión vuelve
    al pool con ``foreign_keys=ON``."""
    with get_engine().connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
        try:
            context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
            with context.begin_transaction():
                context.run_migrations()
                violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
                if violations:
                    raise RuntimeError(f"Claves foráneas rotas tras migrar (tabla, fila, padre): {violations[:10]}")
        finally:
            connection.rollback()
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
