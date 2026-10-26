"""Catálogo de motores de util_bbdd traducido a tipos propios (Fase 2).

Combina ``get_db_type_info_static`` (ficha y ``connection_params``), ``is_async_supported``, los motores de
migración (``MigrationPlanner.supported_sources/targets``, util_bbdd 4.3.0, GAPS G4) y el readiness estático en una matriz de capacidades (GAPS G5). Clasifica cada parámetro de
conexión como secreto, host, ruta o bloqueado, porque util_bbdd no lo indica (GAPS G12).
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from functools import cache
from typing import Any, Literal

ParamType = Literal["string", "integer", "float", "boolean", "object"]
ParamKind = Literal["plain", "secret", "host", "path", "blocked"]

#: Drivers que aparecen en ``database_types.json`` pero no se pueden instalar (GAPS G8).
OBSOLETE_DRIVERS: frozenset[str] = frozenset({"cx_Oracle"})

_SECRET: frozenset[str] = frozenset({"password"})
_HOST: frozenset[str] = frozenset({"host"})
_HOST_BY_ENGINE: dict[str, frozenset[str]] = {"oracle": frozenset({"dsn"}), "hsqldb": frozenset({"jdbc_url"})}
_PATH: frozenset[str] = frozenset({"ssl_ca", "ssl_cert", "ssl_key", "unix_socket", "oracle_client_path", "jdbc_jar"})
_PATH_BY_ENGINE: dict[str, frozenset[str]] = {"sqlite": frozenset({"database"})}
#: ``init_command`` ejecuta SQL arbitrario al conectar: saltaría la protección ``read_only`` de la aplicación.
_BLOCKED: frozenset[str] = frozenset({"init_command"})

#: Todos los parámetros conocidos de util_bbdd 4.0.0. Un test avisa si la librería añade uno sin clasificar.
KNOWN_PARAMS: frozenset[str] = frozenset(
    {
        "host", "port", "user", "password", "database", "schema", "dbname", "dsn", "service_name", "sid",
        "protocol", "encoding", "charset", "autocommit", "connect_timeout", "read_timeout", "write_timeout",
        "timeout", "login_timeout", "pool_size", "pool_name", "pool_timeout", "pool_recycle", "max_overflow",
        "max_idle", "max_lifetime", "close_timeout", "encoding_errors", "catalog_charset_mode", "ssl", "ssl_ca",
        "ssl_cert", "ssl_key", "ssl_verify_cert", "ssl_verify_identity", "sslmode", "unix_socket", "init_command",
        "application_name", "fallback_application_name", "keepalives", "tcp_keepalives_idle",
        "tcp_keepalives_interval", "tcp_keepalives_count", "options", "target_session_attrs", "oracle_client_path",
        "oracle_thick_mode", "as_dict", "encryption", "trust_cert", "use_mars", "sql_server_driver",
        "driver_name", "jdbc_driver", "jdbc_url", "jdbc_jar", "connection_properties", "check_same_thread",
        "isolation_level", "cached_statements",
    }
)  # fmt: skip


@dataclass(frozen=True)
class ParamSpec:
    """Parámetro de conexión de un motor.

    Attributes:
        kind: ``secret`` (se cifra, nunca se devuelve), ``host`` (pasa por la allowlist), ``path`` (debe estar
            dentro de ``UBW_FILES_DIR``), ``blocked`` (no se admite) o ``plain``.
    """

    name: str
    type: ParamType
    required: bool
    default: Any
    options: tuple[str, ...] | None
    description: str
    kind: ParamKind


@dataclass(frozen=True)
class DriverStatus:
    """Driver declarado por util_bbdd y si su módulo está instalado (GAPS G10)."""

    name: str
    installed: bool


@dataclass(frozen=True)
class EngineCapabilities:
    """Matriz de capacidades verificadas (GAPS G5). Las operaciones de fases futuras se añaden al verificarlas."""

    async_supported: bool
    migrate_source: bool
    migrate_target: bool
    readiness: bool


@dataclass(frozen=True)
class EngineSummary:
    """Motor en el catálogo."""

    db_type: str
    name: str
    description: str
    version_range: str
    default_port: int | None
    drivers: tuple[DriverStatus, ...]
    capabilities: EngineCapabilities


@dataclass(frozen=True)
class EngineDetail(EngineSummary):
    """Ficha completa de un motor."""

    url_docs: str | None
    features: tuple[str, ...]
    driver_package: str | None
    install_command: str | None
    system_requirements: tuple[str, ...]
    params: tuple[ParamSpec, ...]


@cache
def migration_engines() -> tuple[frozenset[str], frozenset[str]]:
    """Motores origen y destino de ``MigrationPlanner`` (API pública desde util_bbdd 4.3.0, GAPS G4)."""
    from util_bbdd.migrate import MigrationPlanner

    return frozenset(MigrationPlanner.supported_sources()), frozenset(MigrationPlanner.supported_targets())


class UnknownEngineError(LookupError):
    """``db_type`` no soportado por util_bbdd."""


def param_kind(db_type: str, name: str) -> ParamKind:
    """Clasificación de un parámetro de conexión."""
    if name in _SECRET:
        return "secret"
    if name in _BLOCKED:
        return "blocked"
    if name in _HOST or name in _HOST_BY_ENGINE.get(db_type, frozenset()):
        return "host"
    if name in _PATH or name in _PATH_BY_ENGINE.get(db_type, frozenset()):
        return "path"
    return "plain"


def _driver_installed(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _param_type(raw: object) -> ParamType:
    return raw if raw in ("string", "integer", "float", "boolean", "object") else "string"


def _params(db_type: str, connection_params: dict[str, Any]) -> tuple[ParamSpec, ...]:
    required: list[str] = list(connection_params.get("required", []))
    optional: dict[str, dict[str, Any]] = {o["name"]: o for o in connection_params.get("optional", [])}
    names = required + [n for n in optional if n not in required]
    specs = []
    for name in names:
        info = optional.get(name, {})
        options = info.get("options")
        specs.append(
            ParamSpec(
                name=name,
                type=_param_type(info.get("type", "integer" if name == "port" else "string")),
                required=name in required,
                default=info.get("default"),
                options=tuple(str(o) for o in options) if options else None,
                description=str(info.get("description") or ""),
                kind=param_kind(db_type, name),
            )
        )
    return tuple(specs)


def _driver_info(raw: object) -> dict[str, Any]:
    """``driver_info`` es un ``dict`` salvo en SQL Server, que lista una opción por driver (GAPS G14): se toma la
    primera, que es la predeterminada."""
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    return raw if isinstance(raw, dict) else {}


def _readiness_supported(db_type: str) -> bool:
    from util_bbdd.connection import EngineReadinessAdvisor

    try:
        return bool(EngineReadinessAdvisor().assess(db_type, {}).supported)
    except Exception:  # un motor sin checks no debe romper el catálogo
        return False


def _raw_info(db_type: str) -> dict[str, Any]:
    from util_bbdd import SyncDatabaseManager

    if db_type not in SyncDatabaseManager.get_supported_db_types():
        raise UnknownEngineError(db_type)
    return dict(SyncDatabaseManager.get_db_type_info_static(db_type))


@cache
def engine_detail(db_type: str) -> EngineDetail:
    """Ficha completa de ``db_type`` (cacheada: depende solo de la versión instalada).

    Raises:
        UnknownEngineError: Motor no soportado.
    """
    from util_bbdd.core.capabilities import is_async_supported

    info = _raw_info(db_type)
    driver_info = _driver_info(info.get("driver_info"))
    drivers = tuple(
        DriverStatus(name=name, installed=_driver_installed(name))
        for name in info.get("drivers", [])
        if name not in OBSOLETE_DRIVERS
    )
    port = info.get("default_port")
    return EngineDetail(
        db_type=db_type,
        name=str(info.get("name", db_type)),
        description=str(info.get("description", "")),
        version_range=str(info.get("version_range", "")),
        default_port=port if isinstance(port, int) and port > 0 else None,
        drivers=drivers,
        capabilities=EngineCapabilities(
            async_supported=bool(is_async_supported(db_type)),
            migrate_source=db_type in migration_engines()[0],
            migrate_target=db_type in migration_engines()[1],
            readiness=_readiness_supported(db_type),
        ),
        url_docs=info.get("url_docs"),
        features=tuple(str(f) for f in info.get("supported_features", [])),
        driver_package=driver_info.get("pip_package"),
        install_command=driver_info.get("install_command"),
        system_requirements=tuple(str(r) for r in driver_info.get("system_requirements", [])),
        params=_params(db_type, info.get("connection_params") or {}),
    )


def list_engines() -> list[EngineDetail]:
    """Todos los motores soportados, en el orden de util_bbdd."""
    from util_bbdd import SyncDatabaseManager

    return [engine_detail(db_type) for db_type in SyncDatabaseManager.get_supported_db_types()]


class InvalidParamsError(ValueError):
    """``build_conn_params`` rechaza los parámetros (faltan requeridos o combinación no válida)."""


def build_params(db_type: str, params: dict[str, Any]) -> dict[str, Any]:
    """``conn_params`` para ``SyncDatabaseManager``: los normalizados por util_bbdd más los opcionales del usuario.

    ``build_conn_params`` valida requeridos pero descarta opcionales como ``sslmode``; por eso se superponen.

    Raises:
        InvalidParamsError: Con el mensaje de util_bbdd (no contiene secretos: solo nombres de parámetros).
    """
    from util_bbdd.connection.builder import build_conn_params

    try:
        built = build_conn_params(db_type, **params)
    except ValueError as exc:
        raise InvalidParamsError(str(exc)) from None
    return {**built, **params}
