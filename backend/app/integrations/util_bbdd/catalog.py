"""Catálogo de motores de util_bbdd traducido a tipos propios (Fase 2).

Combina ``get_db_type_info_static`` (ficha, ``connection_params`` y ``default_driver``), la matriz de capacidades
``get_engine_capabilities`` y el estado de los drivers ``get_driver_status`` (util_bbdd 4.6.0, GAPS G5, G8, G10 y G14).
Los motores de migración salen de ``MigrationPlanner.supported_sources/targets`` (util_bbdd 4.3.0, GAPS G4). La clase
de cada parámetro de conexión (secreto, host, puerto, ruta, bloqueado) sale de ``connection_params.kinds`` (util_bbdd
4.6.0, GAPS G12); un parámetro sin clase se trata como bloqueado.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from functools import cache
from typing import Any, Literal, get_args

ParamType = Literal["string", "integer", "float", "boolean", "object"]
ParamKind = Literal["plain", "secret", "host", "port", "path", "blocked"]

#: Todos los parámetros conocidos de util_bbdd. Aunque la clase venga de util_bbdd (G12), un test avisa si la librería
#: añade uno: se revisa antes de ofrecerlo en el formulario.
KNOWN_PARAMS: frozenset[str] = frozenset(
    {
        "host", "port", "user", "password", "database", "schema", "dbname", "dsn", "service_name", "sid",
        "protocol", "encoding", "charset", "autocommit", "connect_timeout", "read_timeout", "write_timeout",
        "timeout", "login_timeout", "pool_size", "pool_name", "pool_timeout", "pool_recycle", "max_overflow",
        "max_idle", "max_lifetime", "close_timeout", "catalog_charset_mode", "ssl", "ssl_ca",
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
            dentro de ``UBW_FILES_DIR``), ``blocked`` (no se admite), ``port`` o ``plain``.
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
    """Matriz de capacidades de util_bbdd (``get_engine_capabilities``, GAPS G5): qué operaciones admite el motor."""

    async_supported: bool
    migrate_source: bool
    migrate_target: bool
    readiness: bool
    documentation: bool
    graphs: bool
    compare: bool
    dump: bool
    dump_constraints: bool
    bulk: bool


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


@cache
def _param_kinds(db_type: str) -> dict[str, str]:
    from util_bbdd.connection import ConnectionParamsManager

    return dict(ConnectionParamsManager.param_kinds(db_type))


def param_kind(db_type: str, name: str) -> ParamKind:
    """Clase de un parámetro de conexión según util_bbdd (``connection_params.kinds``, 4.6.0, GAPS G12).

    Un parámetro sin clase (o con una que la web no conoce) se trata como ``blocked``: falla cerrado.
    """
    kind = _param_kinds(db_type).get(name)
    return kind if kind in get_args(ParamKind) else "blocked"  # type: ignore[return-value]


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


def _capabilities(db_type: str) -> EngineCapabilities:
    from util_bbdd.connection import get_engine_capabilities

    caps = get_engine_capabilities(db_type)  # None para un motor desconocido: sin capacidades
    return EngineCapabilities(**{f.name: bool(getattr(caps, f.name, False)) for f in fields(EngineCapabilities)})


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
    from util_bbdd.connection import get_driver_status

    info = _raw_info(db_type)
    default_driver = info.get("default_driver")
    driver_info: dict[str, Any] = default_driver if isinstance(default_driver, dict) else {}
    drivers = tuple(DriverStatus(name=d.name, installed=d.installed) for d in get_driver_status(db_type))
    port = info.get("default_port")
    return EngineDetail(
        db_type=db_type,
        name=str(info.get("name", db_type)),
        description=str(info.get("description", "")),
        version_range=str(info.get("version_range", "")),
        default_port=port if isinstance(port, int) and port > 0 else None,
        drivers=drivers,
        capabilities=_capabilities(db_type),
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
    """``conn_params`` para ``SyncDatabaseManager``, normalizados por util_bbdd.

    Desde util_bbdd 4.6.0 ``build_conn_params`` conserva los opcionales declarados (``sslmode``…, GAPS G15).

    Raises:
        InvalidParamsError: Con el mensaje de util_bbdd (no contiene secretos: solo nombres de parámetros).
    """
    from util_bbdd.connection.builder import build_conn_params

    try:
        return dict(build_conn_params(db_type, **params))
    except ValueError as exc:
        raise InvalidParamsError(str(exc)) from None
