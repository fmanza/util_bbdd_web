"""Nombre del actor en la auditoría: ``audit_log.actor_name`` (ADR-013).

Al borrar un usuario, ``audit_log.actor_user_id`` pasa a ``NULL`` (``ON DELETE SET NULL``); sin una copia del nombre,
sus acciones pasadas aparecerían como del sistema. La columna se rellena con el nombre actual de cada actor.

``ALTER TABLE ... ADD COLUMN`` y ``DROP COLUMN`` (SQLite ≥ 3.35) no recrean ``audit_log`` (ver la 0012).

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-24
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE audit_log ADD COLUMN actor_name VARCHAR(64)")
    op.execute(
        "UPDATE audit_log SET actor_name = (SELECT username FROM users WHERE users.id = audit_log.actor_user_id) "
        "WHERE actor_user_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE audit_log DROP COLUMN actor_name")
