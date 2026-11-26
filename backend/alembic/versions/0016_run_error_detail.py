"""Fallo de una ejecución como clave y parámetros: ``runs.error_detail`` (JSON, ADR-015).

La API compone ``error_message`` en el idioma de quien consulta la ejecución; las anteriores conservan el texto en
español de ``error_message``. ``ADD COLUMN`` y ``DROP COLUMN`` no recrean ``runs``.

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE runs ADD COLUMN error_detail JSON")


def downgrade() -> None:
    op.execute("ALTER TABLE runs DROP COLUMN error_detail")
