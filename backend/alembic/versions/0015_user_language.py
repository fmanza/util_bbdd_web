"""Idioma de la interfaz por usuario: ``users.language`` (``es`` o ``en``).

Como la 0012, ``ALTER TABLE ... ADD COLUMN`` con ``CHECK`` y ``DROP COLUMN`` no recrean ``users``.

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-25
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN language VARCHAR(5) DEFAULT 'es' NOT NULL "
        "CONSTRAINT ck_users_language CHECK (language IN ('es', 'en'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN language")
