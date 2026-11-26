"""Quita las columnas anteriores a los roles (ADR-014): ``users.role``, ``can_run_sql``, ``can_apply_ddl`` y
``can_write_data``. Desde la 2.0.0 solo se escribían para poder volver a la 1.24.0.

``users.role`` tiene la restricción ``ck_users_role`` y SQLite no permite ``DROP COLUMN`` de una columna con
``CHECK``: se recrea ``users`` (crear, copiar, borrar, renombrar). ``alembic/env.py`` migra con ``foreign_keys=OFF``,
así el ``DROP TABLE`` no borra en cascada sesiones, conexiones ni proyectos, y comprueba ``foreign_key_check`` al
terminar. El resto de la tabla (columnas, restricciones, índices) queda igual.

La bajada vuelve a añadir las columnas con ``ADD COLUMN`` (sin recrear la tabla) y las rellena desde el rol, como
hacía la aplicación: así la ``0014`` puede bajar después.

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-26
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = (
    "id, username, display_name, password_hash, is_active, failed_attempts, locked_until, password_changed_at, "
    "created_at, updated_at, storage_quota_mb, color_scheme, role_id, language"
)


def upgrade() -> None:
    conn = op.get_bind()
    if conn.exec_driver_sql("PRAGMA foreign_keys").scalar():
        raise RuntimeError("0017 recrea users: hay que migrar con foreign_keys=OFF (alembic/env.py)")
    op.execute(
        """
        CREATE TABLE users_0017 (
            id INTEGER NOT NULL,
            username VARCHAR(64) NOT NULL,
            display_name VARCHAR(128) NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            is_active BOOLEAN NOT NULL,
            failed_attempts INTEGER NOT NULL,
            locked_until DATETIME,
            password_changed_at DATETIME NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            storage_quota_mb INTEGER,
            color_scheme VARCHAR(8) DEFAULT 'auto' NOT NULL
                CONSTRAINT ck_users_color_scheme CHECK (color_scheme IN ('light', 'dark', 'auto')),
            role_id INTEGER,
            language VARCHAR(5) DEFAULT 'es' NOT NULL CONSTRAINT ck_users_language CHECK (language IN ('es', 'en')),
            CONSTRAINT pk_users PRIMARY KEY (id),
            CONSTRAINT uq_users_username UNIQUE (username)
        )
        """
    )
    op.execute(f"INSERT INTO users_0017 ({_COLUMNS}) SELECT {_COLUMNS} FROM users")  # noqa: S608 (columnas fijas)
    op.execute("DROP TABLE users")
    op.execute("ALTER TABLE users_0017 RENAME TO users")
    op.execute("CREATE INDEX ix_users_role_id ON users (role_id)")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN role VARCHAR(16) NOT NULL DEFAULT 'user' "
        "CONSTRAINT ck_users_role CHECK (role IN ('admin', 'user'))"
    )
    for column in ("can_run_sql", "can_apply_ddl", "can_write_data"):
        op.execute(f"ALTER TABLE users ADD COLUMN {column} BOOLEAN DEFAULT 0 NOT NULL")
    conn = op.get_bind()
    for user_id, builtin, permissions in conn.execute(
        sa.text("SELECT u.id, r.builtin, r.permissions FROM users u JOIN roles r ON r.id = u.role_id")
    ).all():
        granted = set(json.loads(permissions) if isinstance(permissions, str) else permissions or [])
        admin = builtin == "admin"
        conn.execute(
            sa.text(
                "UPDATE users SET role = :role, can_run_sql = :sql, can_apply_ddl = :ddl, can_write_data = :data "
                "WHERE id = :id"
            ),
            {
                "role": "admin" if admin else "user",
                "sql": admin or "sql.run" in granted,
                "ddl": admin or "ddl.apply" in granted,
                "data": admin or "data.write" in granted,
                "id": user_id,
            },
        )
