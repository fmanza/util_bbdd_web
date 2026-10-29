"""Quitar ``encoding_errors`` de las conexiones MariaDB guardadas (util_bbdd 5.0.0, U-8.6; plan W-8.1).

util_bbdd 5.0.0 ya no declara el parámetro (nunca tuvo efecto: ningún driver de MariaDB lo admite), así que
``validate_params`` lo rechaza si un cliente reenvía los ``params`` guardados y la ficha mostraría un parámetro que ya
no existe.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-29
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PARAM = "encoding_errors"
_connections = sa.table(
    "connections",
    sa.column("id", sa.Integer()),
    sa.column("db_type", sa.String()),
    sa.column("params", sa.JSON()),
)
_logger = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.select(_connections.c.id, _connections.c.params).where(_connections.c.db_type == "mariadb"))
    cleaned = 0
    for connection_id, params in rows.all():
        if isinstance(params, dict) and _PARAM in params:
            kept = {name: value for name, value in params.items() if name != _PARAM}
            bind.execute(sa.update(_connections).where(_connections.c.id == connection_id).values(params=kept))
            cleaned += 1
    _logger.info("Conexiones MariaDB sin %s: %d", _PARAM, cleaned)


def downgrade() -> None:
    """Sin cambios: el valor borrado no tenía efecto y no se puede recuperar (ni hace falta)."""
