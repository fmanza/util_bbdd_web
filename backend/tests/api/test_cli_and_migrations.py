from __future__ import annotations

import io

import pytest
from sqlalchemy import inspect

from app.cli import main
from app.core.config import Settings
from app.db.session import get_engine
from tests.conftest import run_migrations


def test_create_admin_from_stdin(
    migrated: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("frase-de-paso-admin\n"))

    code = main(["create-admin", "--username", "Jefa", "--password-stdin"])

    assert code == 0
    out = capsys.readouterr()
    assert "jefa" in out.out
    assert "frase-de-paso-admin" not in out.out + out.err


def test_create_admin_rejects_duplicate_and_weak_password(
    migrated: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("frase-de-paso-admin\n"))
    main(["create-admin", "--username", "jefa", "--password-stdin"])
    monkeypatch.setattr("sys.stdin", io.StringIO("frase-de-paso-admin\n"))
    assert main(["create-admin", "--username", "jefa", "--password-stdin"]) == 1

    monkeypatch.setattr("sys.stdin", io.StringIO("corta\n"))
    assert main(["create-admin", "--username", "otra", "--password-stdin"]) == 1
    assert "al menos" in capsys.readouterr().err


def test_migration_upgrade_downgrade_upgrade(settings: Settings) -> None:
    from alembic import command
    from alembic.config import Config

    from tests.conftest import BACKEND_DIR

    run_migrations()
    assert {"users", "sessions", "audit_log"} <= set(inspect(get_engine()).get_table_names())

    command.downgrade(Config(str(BACKEND_DIR / "alembic.ini")), "0001")
    assert "users" not in inspect(get_engine()).get_table_names()

    run_migrations()
    assert "users" in inspect(get_engine()).get_table_names()


def test_migration_0011_drops_encoding_errors_from_mariadb(settings: Settings) -> None:
    """W-8.1: util_bbdd 5.0.0 retira ``encoding_errors``; la 0011 lo quita de las conexiones MariaDB guardadas y no
    toca el resto de claves ni de motores. El ``downgrade`` no cambia nada."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    from tests.conftest import BACKEND_DIR

    run_migrations("0010")
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, username, display_name, password_hash, role, is_active, failed_attempts, "
                "password_changed_at, created_at, updated_at) "
                "VALUES (1, 'jefa', 'Jefa', 'x', 'admin', 1, 0, '2026-10-29', '2026-10-29', '2026-10-29')"
            )
        )
        for connection_id, db_type, params in (
            (1, "mariadb", '{"host": "db", "encoding_errors": "replace", "charset": "utf8mb4"}'),
            (2, "mariadb", '{"host": "db2"}'),
            (3, "mysql", '{"host": "db3", "charset": "utf8mb4"}'),
        ):
            connection.execute(
                text(
                    "INSERT INTO connections (id, owner_id, name, db_type, description, params, visibility, read_only, "
                    "created_at, updated_at) VALUES (:id, 1, :name, :db_type, '', :params, 'private', 1, "
                    "'2026-10-29', '2026-10-29')"
                ),
                {"id": connection_id, "name": f"c{connection_id}", "db_type": db_type, "params": params},
            )

    def stored() -> dict[int, dict[str, object]]:
        import json

        with engine.connect() as connection:
            rows = connection.execute(text("SELECT id, params FROM connections ORDER BY id")).all()
        return {row[0]: json.loads(row[1]) for row in rows}

    after = {
        1: {"host": "db", "charset": "utf8mb4"},
        2: {"host": "db2"},
        3: {"host": "db3", "charset": "utf8mb4"},
    }
    run_migrations()
    assert stored() == after

    command.downgrade(Config(str(BACKEND_DIR / "alembic.ini")), "0010")
    assert stored() == after

    run_migrations()
    assert stored() == after


def _seed_related_rows() -> None:
    """Un usuario con una fila en cada tabla que depende de ``users`` desde la 0004 (``ON DELETE CASCADE`` o
    ``SET NULL``). Solo usa columnas que existen desde entonces."""
    from sqlalchemy import text

    with get_engine().begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, username, display_name, password_hash, role, is_active, failed_attempts, "
                "password_changed_at, created_at, updated_at) "
                "VALUES (1, 'jefa', 'Jefa', 'x', 'admin', 1, 0, '2026-11-23', '2026-11-23', '2026-11-23')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO sessions (id, token_hash, user_id, created_at, last_seen_at, expires_at) "
                "VALUES (1, 'h', 1, '2026-11-23', '2026-11-23', '2026-11-24')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO audit_log (id, ts, actor_user_id, action, outcome) VALUES (1, '2026-11-23', 1, 'x', 'ok')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO connections (id, owner_id, name, db_type, description, params, visibility, read_only, "
                "created_at, updated_at) VALUES (1, 1, 'c', 'sqlite', '', '{}', 'private', 1, '2026-11-23', "
                "'2026-11-23')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO projects (id, owner_id, name, description, created_at, updated_at) "
                "VALUES (1, 1, 'p', '', '2026-11-23', '2026-11-23')"
            )
        )


#: Lo que devuelve ``_related_rows()`` si nada se ha borrado ni ha perdido su usuario.
RELATED_INTACT = ([1], [1], [1], [1])


def _related_rows() -> tuple[object, ...]:
    from sqlalchemy import text

    with get_engine().connect() as connection:
        return (
            connection.execute(text("SELECT user_id FROM sessions")).scalars().all(),
            connection.execute(text("SELECT actor_user_id FROM audit_log")).scalars().all(),
            connection.execute(text("SELECT owner_id FROM connections")).scalars().all(),
            connection.execute(text("SELECT owner_id FROM projects")).scalars().all(),
        )


def test_migration_0012_preserves_related_rows(settings: Settings) -> None:
    """La 0012 añade ``users.color_scheme`` sin recrear ``users``: con ``foreign_keys=ON``, un ``DROP TABLE users``
    (modo batch) borraría en cascada sesiones, conexiones y proyectos y dejaría la auditoría sin autor."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from tests.conftest import BACKEND_DIR

    run_migrations("0011")
    _seed_related_rows()
    engine = get_engine()

    run_migrations()
    assert _related_rows() == RELATED_INTACT
    with engine.connect() as connection:
        assert connection.execute(text("SELECT color_scheme FROM users")).scalar_one() == "auto"
    with pytest.raises(IntegrityError, match="ck_users_color_scheme"), engine.begin() as connection:
        connection.execute(text("UPDATE users SET color_scheme = 'sepia'"))

    command.downgrade(Config(str(BACKEND_DIR / "alembic.ini")), "0011")
    assert "color_scheme" not in {column["name"] for column in inspect(engine).get_columns("users")}
    assert _related_rows() == RELATED_INTACT

    run_migrations()
    assert _related_rows() == RELATED_INTACT


def test_downgrade_to_0004_preserves_related_rows(settings: Settings) -> None:
    """Los ``downgrade`` de la 0005, 0006, 0007 y 0010 quitan columnas de ``users`` con ``DROP COLUMN`` nativo: el
    modo batch recrearía la tabla y su ``DROP TABLE`` borraría en cascada las filas de cada usuario."""
    from alembic import command
    from alembic.config import Config

    from tests.conftest import BACKEND_DIR

    run_migrations()
    _seed_related_rows()

    command.downgrade(Config(str(BACKEND_DIR / "alembic.ini")), "0004")
    columns = {column["name"] for column in inspect(get_engine()).get_columns("users")}
    assert not columns & {"can_run_sql", "can_apply_ddl", "can_write_data", "storage_quota_mb", "color_scheme"}
    assert _related_rows() == RELATED_INTACT

    run_migrations()
    assert _related_rows() == RELATED_INTACT
