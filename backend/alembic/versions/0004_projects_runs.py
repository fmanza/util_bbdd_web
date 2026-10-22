"""Proyectos y ejecuciones (Fase 3): ``projects``, ``project_members``, ``project_connections``, ``runs``,
``artifacts`` y ``workers`` (ADR-002, ADR-005).

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workers",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("pid", sa.Integer(), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workers")),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_projects_owner_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
        sa.UniqueConstraint("owner_id", "name", name="uq_projects_owner_id_name"),
    )
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_projects_owner_id"), ["owner_id"], unique=False)

    op.create_table(
        "project_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("alias", sa.String(length=32), nullable=False),
        sa.Column("added_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["added_by"], ["users.id"], name=op.f("fk_project_connections_added_by_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["connections.id"],
            name=op.f("fk_project_connections_connection_id_connections"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_project_connections_project_id_projects"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_connections")),
        sa.UniqueConstraint("project_id", "alias", name="uq_project_connections_project_id_alias"),
    )
    with op.batch_alter_table("project_connections", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_project_connections_connection_id"), ["connection_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_project_connections_project_id"), ["project_id"], unique=False)

    op.create_table(
        "project_members",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("role IN ('owner', 'editor', 'viewer')", name=op.f("ck_project_members_role")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_project_members_project_id_projects"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_project_members_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("project_id", "user_id", name=op.f("pk_project_members")),
    )
    with op.batch_alter_table("project_members", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_project_members_user_id"), ["user_id"], unique=False)

    op.create_table(
        "runs",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("phase", sa.String(length=16), nullable=True),
        sa.Column("progress_message", sa.String(length=255), nullable=True),
        sa.Column("progress_pct", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=32), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("worker_id", sa.String(length=64), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("workspace_path", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=True),
        sa.Column("relaunched_from", sa.String(length=26), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled', 'purged')", name=op.f("ck_runs_status")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_runs_project_id_projects"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_runs_user_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_runs")),
    )
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.create_index("ix_runs_project_id_created_at", ["project_id", "created_at"], unique=False)
        batch_op.create_index("ix_runs_status_created_at", ["status", "created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_runs_user_id"), ["user_id"], unique=False)

    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=26), nullable=False),
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("mime", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_artifacts_run_id_runs"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifacts")),
        sa.UniqueConstraint("run_id", "path", name="uq_artifacts_run_id_path"),
    )
    with op.batch_alter_table("artifacts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_artifacts_run_id"), ["run_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("artifacts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_artifacts_run_id"))

    op.drop_table("artifacts")
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_runs_user_id"))
        batch_op.drop_index("ix_runs_status_created_at")
        batch_op.drop_index("ix_runs_project_id_created_at")

    op.drop_table("runs")
    with op.batch_alter_table("project_members", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_project_members_user_id"))

    op.drop_table("project_members")
    with op.batch_alter_table("project_connections", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_project_connections_project_id"))
        batch_op.drop_index(batch_op.f("ix_project_connections_connection_id"))

    op.drop_table("project_connections")
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_projects_owner_id"))

    op.drop_table("projects")
    op.drop_table("workers")
