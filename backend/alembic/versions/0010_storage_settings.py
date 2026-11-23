"""Almacenamiento administrable: ``app_settings`` y ``users.storage_quota_mb`` (ADR-012).

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name=op.f("fk_app_settings_updated_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_app_settings")),
    )
    # ``ADD COLUMN`` nativo, como en la 0005-0007 (sin recrear ``users``).
    op.add_column("users", sa.Column("storage_quota_mb", sa.Integer(), nullable=True))


def downgrade() -> None:
    # ``DROP COLUMN`` nativo (SQLite ≥ 3.35), no ``batch_alter_table``: en SQLite el modo batch recrea ``users`` y, con
    # ``foreign_keys=ON`` (``alembic/env.py`` usa el engine de la app), su ``DROP TABLE`` borraría en cascada las filas
    # que dependen de los usuarios (sesiones, conexiones, proyectos…). Ver la 0012.
    op.execute("ALTER TABLE users DROP COLUMN storage_quota_mb")
    op.drop_table("app_settings")
