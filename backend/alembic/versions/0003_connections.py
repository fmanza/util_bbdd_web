"""Conexiones (Fase 2): ``connections`` con secreto cifrado y ``allowlist_entries`` (anti-SSRF).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("db_type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("secret_enc", sa.Text(), nullable=True),
        sa.Column("visibility", sa.String(length=16), nullable=False),
        sa.Column("read_only", sa.Boolean(), nullable=False),
        sa.Column("last_test_at", sa.DateTime(), nullable=True),
        sa.Column("last_test_ok", sa.Boolean(), nullable=True),
        sa.Column("last_test_error", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("visibility IN ('private', 'shared')", name=op.f("ck_connections_visibility")),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_connections_owner_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_connections")),
        sa.UniqueConstraint("owner_id", "name", name="uq_connections_owner_id_name"),
    )
    op.create_index(op.f("ix_connections_owner_id"), "connections", ["owner_id"], unique=False)
    op.create_table(
        "allowlist_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pattern", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_allowlist_entries_created_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_allowlist_entries")),
        sa.UniqueConstraint("pattern", name=op.f("uq_allowlist_entries_pattern")),
    )


def downgrade() -> None:
    op.drop_table("allowlist_entries")
    op.drop_index(op.f("ix_connections_owner_id"), table_name="connections")
    op.drop_table("connections")
