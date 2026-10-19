from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.db.session import SQLITE_PRAGMAS, build_engine


def test_database_url_points_to_config_db(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)

    assert settings.database_url == f"sqlite:///{(tmp_path / 'config.db').as_posix()}"


def test_secrets_are_not_rendered(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, app_secret_key="muy-secreta")  # type: ignore[arg-type]

    assert "muy-secreta" not in repr(settings)


def test_secrets_read_from_docker_secrets_dir(tmp_path: Path) -> None:
    (tmp_path / "ubw_app_secret_key").write_text("desde-secret", encoding="utf-8")

    settings = Settings(_secrets_dir=tmp_path)  # type: ignore[call-arg]

    assert settings.app_secret_key is not None
    assert settings.app_secret_key.get_secret_value() == "desde-secret"


def test_sqlite_pragmas_applied(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{(tmp_path / 'c.db').as_posix()}")
    with engine.connect() as conn:
        journal = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
        fks = conn.exec_driver_sql("PRAGMA foreign_keys").scalar()
    engine.dispose()

    assert len(SQLITE_PRAGMAS) == 4
    assert journal == "wal"
    assert fks == 1


def test_util_bbdd_engines_available() -> None:
    from app.integrations.util_bbdd import supported_db_types

    assert {"oracle", "postgresql", "sqlserver", "sqlite"} <= set(supported_db_types())
