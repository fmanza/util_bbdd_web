"""Tema de la interfaz por usuario: ``users.color_scheme`` (``light``, ``dark`` o ``auto``).

No usa ``batch_alter_table`` ni ``create_check_constraint``: en SQLite recrearían ``users`` y, con
``PRAGMA foreign_keys=ON`` (el engine de la aplicación también lo aplica a las migraciones), el ``DROP TABLE users``
del modo batch dispararía los ``ON DELETE CASCADE`` / ``SET NULL`` de todas las FK hacia ``users`` (sesiones,
conexiones, proyectos, auditoría…). ``ALTER TABLE ... ADD COLUMN`` con ``CHECK`` y ``DROP COLUMN`` (SQLite ≥ 3.35)
no recrean la tabla.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-23
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN color_scheme VARCHAR(8) DEFAULT 'auto' NOT NULL "
        "CONSTRAINT ck_users_color_scheme CHECK (color_scheme IN ('light', 'dark', 'auto'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN color_scheme")
