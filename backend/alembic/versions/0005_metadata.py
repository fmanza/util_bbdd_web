"""Explorador de metadatos (Fase 4): ``metadata_cache``, ``named_queries`` y ``users.can_run_sql``.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "named_queries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("db_type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("sql_template", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_named_queries_created_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_named_queries")),
        sa.UniqueConstraint("db_type", "name", name="uq_named_queries_db_type_name"),
    )
    op.create_table(
        "metadata_cache",
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("schema", sa.String(length=128), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["connections.id"],
            name=op.f("fk_metadata_cache_connection_id_connections"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("connection_id", "schema", name=op.f("pk_metadata_cache")),
    )
    # ``ADD COLUMN`` nativo, no ``batch_alter_table``: con un ``server_default`` de expresión, el modo batch de SQLite
    # recrea ``users`` y su ``DROP TABLE`` borraría en cascada las filas de cada usuario (ver el ``downgrade``).
    op.add_column("users", sa.Column("can_run_sql", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    # ``DROP COLUMN`` nativo (SQLite ≥ 3.35), no ``batch_alter_table``: en SQLite el modo batch recrea ``users`` y, con
    # ``foreign_keys=ON`` (``alembic/env.py`` usa el engine de la app), su ``DROP TABLE`` borraría en cascada las filas
    # que dependen de los usuarios (sesiones, conexiones, proyectos…). Ver la 0012.
    op.execute("ALTER TABLE users DROP COLUMN can_run_sql")

    op.drop_table("metadata_cache")
    op.drop_table("named_queries")
