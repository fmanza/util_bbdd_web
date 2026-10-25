"""Plantillas de documento: ``document_templates`` (Word y Excel de la documentación, ADR-011).

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_templates",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("table_style", sa.String(length=100), nullable=True),
        sa.Column("table_styles", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_document_templates_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_document_templates_created_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_templates")),
    )
    op.create_index(op.f("ix_document_templates_project_id"), "document_templates", ["project_id"])
    # Nombre único por ámbito y tipo sin distinguir mayúsculas; ``coalesce`` porque SQLite trata los NULL (plantillas
    # globales) como distintos en un índice único.
    op.create_index(
        op.f("uq_document_templates_scope_kind_name"),
        "document_templates",
        [sa.text("coalesce(project_id, 0)"), "kind", sa.text("lower(name)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("uq_document_templates_scope_kind_name"), table_name="document_templates")
    op.drop_index(op.f("ix_document_templates_project_id"), table_name="document_templates")
    op.drop_table("document_templates")
