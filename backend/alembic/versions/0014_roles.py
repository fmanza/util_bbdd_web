"""Roles con permisos (ADR-014): tabla ``roles`` y ``users.role_id``.

Crea los roles base «Administrador» (``builtin='admin'``, todos los permisos) y «Usuario» (``builtin='user'``, ninguno)
y asigna a cada usuario el que le da **exactamente** sus permisos de antes:

- ``role='admin'`` → «Administrador», que tiene todos los permisos: los admins sin ``can_*`` ganan SQL libre, aplicar
  DDL y escribir datos (antes podían activárselos a sí mismos; decisión de la sesión 2026-11-25-roles-idioma);
- ``role='user'`` sin ``can_*`` → «Usuario»;
- ``role='user'`` con alguno de ``can_run_sql``, ``can_apply_ddl`` o ``can_write_data`` → un rol por combinación
  («Usuario + SQL», «Usuario + DDL + datos»…) con ``sql.run``, ``ddl.apply`` y ``data.write``.

``users.role`` y ``users.can_*`` se quedan (sin uso; la aplicación los mantiene en sincronía para poder volver a una
imagen anterior). Como en la 0012 y la 0013, nada recrea ``users``: ``role_id`` se añade con ``ALTER TABLE`` y sin
``REFERENCES`` (SQLite no permite después ``DROP COLUMN`` de una columna con FK); la integridad la garantiza la
aplicación (un rol con usuarios no se borra).

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-25
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Columna antigua → (permiso, etiqueta en el nombre del rol generado).
_FLAGS: tuple[tuple[str, str, str], ...] = (
    ("can_run_sql", "sql.run", "SQL"),
    ("can_apply_ddl", "ddl.apply", "DDL"),
    ("can_write_data", "data.write", "datos"),
)


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("builtin", sa.String(8), nullable=True),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("builtin IS NULL OR builtin IN ('admin', 'user')", name="ck_roles_builtin"),
        sa.UniqueConstraint("name", name="uq_roles_name"),
        sa.UniqueConstraint("builtin", name="uq_roles_builtin"),
    )
    op.execute("ALTER TABLE users ADD COLUMN role_id INTEGER")
    op.create_index("ix_users_role_id", "users", ["role_id"])

    conn = op.get_bind()
    now = datetime.now(UTC).isoformat(sep=" ")
    roles = sa.table(
        "roles",
        sa.column("id", sa.Integer()),
        sa.column("name", sa.String()),
        sa.column("builtin", sa.String()),
        sa.column("permissions", sa.JSON()),
        sa.column("created_at", sa.String()),
        sa.column("updated_at", sa.String()),
    )

    def add_role(name: str, builtin: str | None, permissions: list[str]) -> int:
        result = conn.execute(
            roles.insert().values(name=name, builtin=builtin, permissions=permissions, created_at=now, updated_at=now)
        )
        return int(result.lastrowid)

    admin_id = add_role("Administrador", "admin", [])
    user_id = add_role("Usuario", "user", [])
    conn.execute(sa.text("UPDATE users SET role_id = :r WHERE role = 'admin'"), {"r": admin_id})

    rows = conn.execute(
        sa.text("SELECT id, can_run_sql, can_apply_ddl, can_write_data FROM users WHERE role <> 'admin'")
    ).all()
    combos: dict[tuple[str, ...], int] = {}
    for row in rows:
        flags = dict(zip(("can_run_sql", "can_apply_ddl", "can_write_data"), row[1:], strict=True))
        granted = tuple(perm for column, perm, _ in _FLAGS if flags[column])
        if not granted:
            role_id = user_id
        elif granted in combos:
            role_id = combos[granted]
        else:
            labels = [label for column, _, label in _FLAGS if flags[column]]
            role_id = combos[granted] = add_role("Usuario + " + " + ".join(labels), None, list(granted))
        conn.execute(sa.text("UPDATE users SET role_id = :r WHERE id = :u"), {"r": role_id, "u": row[0]})


def downgrade() -> None:
    # Los permisos vuelven a ``users.role`` y ``users.can_*``, que la aplicación mantiene en sincronía; se repasan por
    # si alguien los cambió a mano en la BD.
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
    op.drop_index("ix_users_role_id", table_name="users")
    op.execute("ALTER TABLE users DROP COLUMN role_id")
    op.drop_table("roles")
