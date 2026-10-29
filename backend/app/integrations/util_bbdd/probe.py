"""Prueba de conexión y readiness en un subproceso con timeout (ADR-002, Fase 2).

Usa :func:`isolated.run_isolated`: los ``conn_params`` (con la contraseña) viajan por la tubería, el hijo no
registra nada y al padre solo vuelve un código de error y el tipo de la excepción, nunca su mensaje.

La prueba hace ``ping()`` (util_bbdd 4.6.0, GAPS G13; también en HSQLDB, sin SQLAlchemy). La versión del servidor sale
de SQLAlchemy si el motor lo tiene: ``get_server_version()`` es menos precisa en Oracle (``23.0.0.0.0`` frente a
``23.26.3.0.0``) y añade sufijos en MariaDB y PostgreSQL; sin SQLAlchemy (HSQLDB), la de util_bbdd.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from app.integrations.util_bbdd.isolated import TaskResult, run_isolated

ErrorCode = Literal["driver_missing", "invalid_config", "connection_failed", "timeout", "unknown"]
MAX_SERVER_VERSION = 200

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProbeError:
    """Fallo saneado: ``code`` para el usuario y ``exc_type`` solo para el log."""

    code: ErrorCode
    exc_type: str


@dataclass(frozen=True)
class ConnectionCheck:
    """Resultado de una prueba de conexión."""

    ok: bool
    duration_ms: int
    server_version: str | None
    error: ProbeError | None


@dataclass(frozen=True)
class ReadinessFinding:
    """Hallazgo de ``EngineReadinessAdvisor``."""

    level: str
    param: str
    current: str
    recommendation: str


@dataclass(frozen=True)
class ReadinessResult:
    """Informe de readiness (``EngineReadinessReport``) o el error que impidió obtenerlo."""

    supported: bool
    dynamic: bool
    detail: str | None
    checked_at: datetime | None
    findings: tuple[ReadinessFinding, ...]
    error: ProbeError | None


def _sqlalchemy_version(manager: Any) -> str | None:
    try:
        engine = manager.get_sqlalchemy_engine()
        with engine.connect():
            info = engine.dialect.server_version_info
    except Exception:  # sin SQLAlchemy (HSQLDB): se pregunta a util_bbdd
        return None
    return ".".join(str(part) for part in info) if info else None


def _server_version(manager: Any) -> str | None:
    """Versión del servidor: la numérica de SQLAlchemy o, sin ella, ``get_server_version()`` (recortada)."""
    version = _sqlalchemy_version(manager)
    if version:
        return version
    try:
        version = manager.get_server_version()
    except Exception:  # la versión es informativa: su fallo no invalida la prueba
        return None
    return str(version)[:MAX_SERVER_VERSION] if version else None


def test_task(db_type: str, conn_params: dict[str, Any]) -> dict[str, Any]:
    """Tarea del subproceso: ``ping()`` y versión del servidor."""
    from util_bbdd import SyncDatabaseManager

    with SyncDatabaseManager(db_type, conn_params, use_pool=False) as manager:
        manager.ping()
        return {"server_version": _server_version(manager)}


def readiness_task(db_type: str, conn_params: dict[str, Any]) -> dict[str, Any]:
    """Tarea del subproceso: ``get_engine_readiness()``."""
    from util_bbdd import SyncDatabaseManager

    with SyncDatabaseManager(db_type, conn_params, use_pool=False) as manager:
        report = manager.get_engine_readiness()
        return {
            "supported": report.supported,
            "dynamic": report.dynamic,
            "detail": report.error,  # util_bbdd solo pone aquí el tipo de la excepción
            "checked_at": report.checked_at,
            "findings": [(f.level, f.param, str(f.current), str(f.recommendation)) for f in report.findings],
        }


def _error(result: TaskResult) -> ProbeError | None:
    if result.error is None:
        return None
    code = result.error.code if result.error.code in _PROBE_CODES else "unknown"
    return ProbeError(code=code, exc_type=result.error.exc_type)  # type: ignore[arg-type]


_PROBE_CODES = frozenset({"driver_missing", "invalid_config", "connection_failed", "timeout", "unknown"})


def check_connection(db_type: str, conn_params: dict[str, Any], *, timeout: float) -> ConnectionCheck:
    """Conecta con ``SyncDatabaseManager(db_type, conn_params, use_pool=False)`` y lee la versión del servidor."""
    result = run_isolated(f"{__name__}:test_task", {"db_type": db_type, "conn_params": conn_params}, timeout=timeout)
    value = result.value or {}
    return ConnectionCheck(
        ok=result.ok,
        duration_ms=result.duration_ms,
        server_version=value.get("server_version"),
        error=_error(result),
    )


def engine_readiness(db_type: str, conn_params: dict[str, Any], *, timeout: float) -> ReadinessResult:
    """``SyncDatabaseManager.get_engine_readiness()`` en el subproceso."""
    result = run_isolated(
        f"{__name__}:readiness_task", {"db_type": db_type, "conn_params": conn_params}, timeout=timeout
    )
    value = result.value or {}
    return ReadinessResult(
        supported=bool(value.get("supported", False)),
        dynamic=bool(value.get("dynamic", False)),
        detail=value.get("detail"),
        checked_at=value.get("checked_at"),
        findings=tuple(ReadinessFinding(*f) for f in value.get("findings", [])),
        error=_error(result),
    )
