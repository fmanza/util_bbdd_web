"""Volcado de datos (Fase 8): ``users.can_write_data`` (permiso para volcar filas en una BD destino, ADR-009).

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ``ADD COLUMN`` nativo, no ``batch_alter_table``: con un ``server_default`` de expresión, el modo batch de SQLite
    # recrea ``users`` y su ``DROP TABLE`` borraría en cascada las filas de cada usuario (ver el ``downgrade``).
    op.add_column("users", sa.Column("can_write_data", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    # ``DROP COLUMN`` nativo (SQLite ≥ 3.35), no ``batch_alter_table``: en SQLite el modo batch recrea ``users`` y, con
    # ``foreign_keys=ON`` (``alembic/env.py`` usa el engine de la app), su ``DROP TABLE`` borraría en cascada las filas
    # que dependen de los usuarios (sesiones, conexiones, proyectos…). Ver la 0012.
    op.execute("ALTER TABLE users DROP COLUMN can_write_data")
