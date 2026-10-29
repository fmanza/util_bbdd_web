"""Reglas puras de conexiones: cifrado, allowlist, hosts de destino, validación de parámetros y catálogo."""

from __future__ import annotations

import ipaddress
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from app.core.config import Settings
from app.domain.connections.allowlist import (
    IPAddress,
    build_policy,
    is_allowed,
    normalize_pattern,
    target_hosts,
)
from app.domain.connections.crypto import SecretBox, SecretDecryptError, parse_keys
from app.domain.connections.errors import ConnectionParamsError, InvalidAllowlistPatternError
from app.domain.connections.params import resolve_paths, validate_params, with_timeouts
from app.integrations.util_bbdd.catalog import (
    KNOWN_PARAMS,
    InvalidParamsError,
    build_params,
    engine_detail,
    list_engines,
    migration_engines,
)

# --- cifrado -----------------------------------------------------------------------------------------------------


def test_secret_box_roundtrip_hides_plaintext() -> None:
    box = SecretBox([Fernet.generate_key().decode()])

    token = box.encrypt({"password": "muy-secreta"})

    assert "muy-secreta" not in token
    assert box.decrypt(token) == {"password": "muy-secreta"}


def test_rotation_reencrypts_with_primary_key() -> None:
    old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    token = SecretBox([old]).encrypt({"password": "x"})

    rotated = SecretBox(parse_keys(f"{new}, {old}")).rotate(token)

    assert SecretBox([new]).decrypt(rotated) == {"password": "x"}
    with pytest.raises(SecretDecryptError):
        SecretBox([new]).decrypt(token)


# --- allowlist ---------------------------------------------------------------------------------------------------


def _resolver(mapping: dict[str, list[str]]):  # type: ignore[no-untyped-def]
    def resolve(host: str) -> list[IPAddress]:
        if host not in mapping:
            raise OSError("no resuelve")
        return [ipaddress.ip_address(ip) for ip in mapping[host]]

    return resolve


DNS = _resolver(
    {
        "db.corp.local": ["10.1.2.3"],
        "corp.local": ["10.1.0.1"],
        "public.example": ["93.184.216.34"],
        "localhost": ["127.0.0.1"],
        "metadata": ["169.254.169.254"],
        "mixed.corp.local": ["10.1.2.4", "93.184.216.35"],
        "10.9.9.9": ["10.9.9.9"],
        "mapped": ["::ffff:169.254.169.254"],
    }
)


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [("10.0.0.0/8", "10.0.0.0/8"), ("10.1.2.3", "10.1.2.3/32"), ("DB.Corp.Local", "db.corp.local"), ("*", "*")],
)
def test_normalize_pattern(raw: str, normalized: str) -> None:
    assert normalize_pattern(raw) == normalized


@pytest.mark.parametrize("raw", ["", "http://x", "a b", "*.*.x", "-bad.example"])
def test_invalid_patterns_rejected(raw: str) -> None:
    with pytest.raises(InvalidAllowlistPatternError):
        normalize_pattern(raw)


def test_empty_allowlist_denies_everything() -> None:
    assert not is_allowed("db.corp.local", build_policy([]), DNS)


@pytest.mark.parametrize(
    ("patterns", "host", "allowed"),
    [
        (["10.0.0.0/8"], "db.corp.local", True),
        (["db.corp.local"], "db.corp.local", True),
        (["*.corp.local"], "db.corp.local", True),
        (["*.corp.local"], "corp.local", False),
        (["*"], "public.example", True),
        (["10.0.0.0/8"], "public.example", False),
        (["10.0.0.0/8"], "mixed.corp.local", False),
        (["10.0.0.0/8"], "10.9.9.9", True),
        (["*"], "localhost", False),
        (["127.0.0.1/32"], "localhost", True),
        (["*", "169.254.0.0/16"], "metadata", False),
        (["*"], "mapped", False),
        (["*"], "no-resuelve.example", False),
    ],
)
def test_allowlist_policy(patterns: list[str], host: str, allowed: bool) -> None:
    assert is_allowed(host, build_policy(patterns), DNS) is allowed


@pytest.mark.parametrize(
    ("db_type", "params", "hosts"),
    [
        ("postgresql", {"host": "db1"}, ["db1"]),
        ("oracle", {"dsn": "ora.corp:1521/FREEPDB1"}, ["ora.corp"]),
        ("oracle", {"dsn": "tcps://ora.corp:2484/svc"}, ["ora.corp"]),
        ("oracle", {"dsn": "(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=a.corp)(PORT=1521)))"}, ["a.corp"]),
        ("oracle", {"host": "ora2", "service_name": "x"}, ["ora2"]),
        ("hsqldb", {"jdbc_url": "jdbc:hsqldb:hsql://hs.corp:9001/db"}, ["hs.corp"]),
        ("hsqldb", {"jdbc_url": "jdbc:hsqldb:mem:test"}, []),
        ("sqlite", {"database": "/x.db", "host": "ignorado"}, []),
    ],
)
def test_target_hosts(db_type: str, params: dict[str, str], hosts: list[str]) -> None:
    assert target_hosts(db_type, params) == hosts


# --- parámetros --------------------------------------------------------------------------------------------------


@pytest.fixture
def files_settings(tmp_path: Path) -> Settings:
    (tmp_path / "files").mkdir()
    return Settings(files_dir=tmp_path / "files", environment="production")


@pytest.mark.parametrize(
    ("db_type", "params", "fragment"),
    [
        ("postgresql", {"nope": 1}, "no es un parámetro"),
        ("postgresql", {"password": "x"}, "campo «password»"),
        ("mariadb", {"init_command": "SET x=1"}, "por seguridad"),
        ("mariadb", {"encoding_errors": "replace"}, "no es un parámetro"),  # retirado en util_bbdd 5.0.0 (W-8.1)
        ("postgresql", {"port": "5432"}, "integer"),
        ("postgresql", {"port": True}, "integer"),
        ("postgresql", {"sslmode": "siempre"}, "debe ser uno de"),
        ("sqlite", {"database": "../config.db"}, "UBW_FILES_DIR"),
        ("sqlite", {"database": "/etc/passwd"}, "UBW_FILES_DIR"),
        ("sqlite", {"database": ":memory:"}, "memoria"),
        ("mysql", {"ssl_key": "../../secrets/app_secret_key.txt"}, "UBW_FILES_DIR"),
        ("hsqldb", {"jdbc_url": "jdbc:hsqldb:res:/x"}, "jdbc_url"),
        ("hsqldb", {"jdbc_url": "jdbc:hsqldb:file:../../data/x"}, "UBW_FILES_DIR"),
    ],
)
def test_invalid_params_rejected(
    files_settings: Settings, db_type: str, params: dict[str, object], fragment: str
) -> None:
    with pytest.raises(ConnectionParamsError) as info:
        validate_params(engine_detail(db_type), params, files_settings)

    assert fragment in (info.value.detail or "")


def test_valid_params_are_normalized(files_settings: Settings) -> None:
    files = files_settings.files_dir

    pg = validate_params(
        engine_detail("postgresql"), {"host": "db", "port": 5433, "sslmode": "require", "schema": ""}, files_settings
    )
    lite = validate_params(engine_detail("sqlite"), {"database": str(files / "sub" / "a.db")}, files_settings)
    hs = validate_params(engine_detail("hsqldb"), {"jdbc_url": "jdbc:hsqldb:file:dbs/x;shutdown=true"}, files_settings)

    assert pg == {"host": "db", "port": 5433, "sslmode": "require"}
    assert lite == {"database": "sub/a.db"}
    assert hs == {"jdbc_url": "jdbc:hsqldb:file:dbs/x;shutdown=true"}
    assert resolve_paths(engine_detail("sqlite"), lite, files_settings) == {
        "database": str(files.resolve() / "sub/a.db")
    }


def test_connect_timeouts_injected_only_when_missing() -> None:
    assert with_timeouts("sqlserver", {"host": "x"})["login_timeout"] == 10
    assert with_timeouts("postgresql", {"connect_timeout": 3})["connect_timeout"] == 3
    assert "connect_timeout" not in with_timeouts("sqlite", {})


# --- catálogo (capa anticorrupción) ------------------------------------------------------------------------------


def test_catalog_lists_all_util_bbdd_engines() -> None:
    engines = {e.db_type: e for e in list_engines()}

    assert set(engines) == {"mariadb", "mysql", "oracle", "postgresql", "hsqldb", "sqlserver", "sqlite"}
    assert engines["postgresql"].default_port == 5432
    assert engines["sqlite"].default_port is None
    assert engines["hsqldb"].capabilities.async_supported is False
    assert engines["sqlserver"].driver_package == "pymssql"  # default_driver también en SQL Server (G14)
    assert "cx_Oracle" not in {d.name for d in engines["oracle"].drivers}  # G8
    # G5: sin SQLAlchemy, HSQLDB no compara, ni vuelca ni carga; SQLite vuelca sin gestionar constraints.
    hsqldb, sqlite = engines["hsqldb"].capabilities, engines["sqlite"].capabilities
    assert (hsqldb.documentation, hsqldb.compare, hsqldb.dump, hsqldb.bulk) == (True, False, False, False)
    assert (sqlite.dump, sqlite.dump_constraints, sqlite.migrate_source) == (True, False, False)
    assert next(d for d in engines["sqlite"].drivers if d.name == "sqlite3").installed


def test_every_util_bbdd_param_is_classified() -> None:
    names = {p.name for e in list_engines() for p in e.params}

    assert names <= KNOWN_PARAMS, f"Parámetros nuevos sin clasificar (GAPS G12): {sorted(names - KNOWN_PARAMS)}"
    assert {p.kind for p in engine_detail("postgresql").params if p.name == "password"} == {"secret"}
    assert {p.kind for p in engine_detail("sqlite").params if p.name == "database"} == {"path"}


def test_param_kinds_come_from_util_bbdd() -> None:
    """Contrato G12: util_bbdd da clase a todos los parámetros declarados, de las que conoce la web; uno sin clase se
    trata como ``blocked`` (falla cerrado)."""
    from typing import get_args

    from util_bbdd.connection import ConnectionParamsManager

    from app.integrations.util_bbdd.catalog import ParamKind, param_kind

    for engine in list_engines():
        kinds = ConnectionParamsManager.param_kinds(engine.db_type)
        assert {p.name for p in engine.params} <= set(kinds), engine.db_type
        assert set(kinds.values()) <= set(get_args(ParamKind)), engine.db_type
    expected = {("oracle", "dsn"): "host", ("hsqldb", "jdbc_url"): "host", ("mariadb", "init_command"): "blocked",
                ("postgresql", "port"): "port", ("mysql", "ssl_ca"): "path", ("postgresql", "sslmode"): "plain"}  # fmt: skip
    assert {key: param_kind(*key) for key in expected} == expected
    assert param_kind("postgresql", "inventado") == "blocked"


def test_migration_engines_come_from_util_bbdd_and_match_the_form() -> None:
    from typing import get_args

    from app.domain.runs.operations import MigrationEngine

    sources, targets = migration_engines()

    assert {"oracle", "postgresql"} <= sources and "sqlite" not in sources
    assert set(get_args(MigrationEngine)) == targets, "El Literal del formulario debe ofrecer los destinos de util_bbdd"
    assert engine_detail("oracle").capabilities.migrate_source
    assert not engine_detail("sqlite").capabilities.migrate_target


def test_build_params_reports_missing_required_without_secrets() -> None:
    with pytest.raises(InvalidParamsError) as info:
        build_params("postgresql", {"host": "db", "password": "no-mostrar"})

    assert "user" in str(info.value)
    assert "no-mostrar" not in str(info.value)
    assert (
        build_params("postgresql", {"host": "h", "user": "u", "password": "p", "database": "d", "sslmode": "require"})[
            "sslmode"
        ]
        == "require"
    )


def test_capabilities_mirror_util_bbdd() -> None:
    """Contrato G5: cada capacidad de la web existe en ``get_engine_capabilities`` (si util_bbdd renombra una, falla
    aquí en lugar de quedarse en ``False``) y coincide con ella en todos los motores."""
    import dataclasses

    from util_bbdd.connection import get_engine_capabilities

    from app.integrations.util_bbdd.catalog import EngineCapabilities

    ours = {f.name for f in dataclasses.fields(EngineCapabilities)}
    for engine in list_engines():
        theirs = dataclasses.asdict(get_engine_capabilities(engine.db_type))  # type: ignore[arg-type]
        assert ours <= set(theirs), sorted(ours - set(theirs))
        assert dataclasses.asdict(engine.capabilities) == {name: theirs[name] for name in ours}


def test_probe_takes_the_version_from_util_bbdd() -> None:
    """G43 (util_bbdd 5.0.0, W-8.3): la versión es la numérica de ``get_server_version_info()``; si el servidor no da
    números (o ``None``), el texto de ``get_server_version()``, recortado. Sin SQLAlchemy y sin romper la prueba."""
    from unittest.mock import MagicMock

    from app.integrations.util_bbdd.probe import MAX_SERVER_VERSION, _server_version

    numeric = MagicMock()
    numeric.get_server_version_info.return_value = (23, 26, 3, 0, 0)
    text_only = MagicMock()
    text_only.get_server_version_info.return_value = None
    text_only.get_server_version.return_value = "HSQL " + "x" * 300
    missing = MagicMock()
    missing.get_server_version_info.return_value = None
    missing.get_server_version.return_value = None
    broken = MagicMock()
    broken.get_server_version_info.side_effect = RuntimeError

    assert _server_version(numeric) == "23.26.3.0.0"
    numeric.get_server_version.assert_not_called()
    numeric.get_sqlalchemy_engine.assert_not_called()
    assert _server_version(text_only) == ("HSQL " + "x" * 300)[:MAX_SERVER_VERSION]
    assert _server_version(missing) is None
    assert _server_version(broken) is None


def test_probe_task_pings_sqlite(tmp_path: Path) -> None:
    import sqlite3

    from app.integrations.util_bbdd.probe import test_task

    database = tmp_path / "x.db"
    sqlite3.connect(database).close()

    assert test_task("sqlite", build_params("sqlite", {"database": str(database)}))["server_version"]
