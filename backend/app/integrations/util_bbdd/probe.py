"""Prueba de conexión y readiness en un subproceso con timeout (ADR-002, Fase 2).

Cada prueba corre en un proceso hijo (*spawn*) que se mata si supera el timeout: un driver colgado no bloquea la
API. Los ``conn_params`` (con la contraseña) viajan por la tubería de ``multiprocessing``, nunca por argv ni por el
entorno. El hijo desactiva el logging y la salida estándar, porque util_bbdd y los drivers pueden escribir la URL de
conexión; al padre solo vuelve un código de error y el tipo de la excepción, nunca su mensaje.
"""

from __future__ import annotations

import contextlib
import io
import logging
import multiprocessing
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from multiprocessing.connection import Connection
from typing import Any, Literal

ProbeKind = Literal["test", "readiness"]
ErrorCode = Literal["driver_missing", "invalid_config", "connection_failed", "timeout", "unknown"]

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


def _classify(exc: BaseException) -> ErrorCode:
    from util_bbdd import exceptions as e

    if isinstance(exc, e.DriverError | ImportError | ModuleNotFoundError):
        return "driver_missing"
    if isinstance(exc, e.QueryTimeoutError | e.PoolTimeoutError | TimeoutError):
        return "timeout"
    if isinstance(exc, e.ValidationError | e.InvalidConnectionConfig | ValueError | TypeError | KeyError):
        return "invalid_config"
    if isinstance(exc, e.ConnectionError | e.PoolConnectionError | e.DatabaseConfigurationError | OSError):
        return "connection_failed"
    return "unknown"


def _server_version(manager: Any) -> str | None:
    try:
        engine = manager.get_sqlalchemy_engine()
        with engine.connect():
            info = engine.dialect.server_version_info
        return ".".join(str(part) for part in info) if info else None
    except Exception:  # la versión es informativa: su fallo no invalida la prueba
        return None


def _child(send: Connection, kind: ProbeKind, db_type: str, conn_params: dict[str, Any]) -> None:
    """Proceso hijo: conecta con util_bbdd y devuelve un ``dict`` sin secretos ni mensajes de excepción."""
    logging.disable(logging.CRITICAL)
    sys.stdout = sys.stderr = io.StringIO()
    start = time.monotonic()
    payload: dict[str, Any]
    try:
        from util_bbdd import SyncDatabaseManager

        with SyncDatabaseManager(db_type, conn_params, use_pool=False) as manager:
            if kind == "test":
                payload = {"ok": True, "server_version": _server_version(manager)}
            else:
                report = manager.get_engine_readiness()
                payload = {
                    "ok": True,
                    "supported": report.supported,
                    "dynamic": report.dynamic,
                    "detail": report.error,  # util_bbdd solo pone aquí el tipo de la excepción
                    "checked_at": report.checked_at,
                    "findings": [(f.level, f.param, str(f.current), str(f.recommendation)) for f in report.findings],
                }
    except BaseException as exc:  # frontera del proceso: todo se reduce a un código
        payload = {"ok": False, "error": (_classify(exc), type(exc).__name__)}
    payload["duration_ms"] = int((time.monotonic() - start) * 1000)
    with contextlib.suppress(Exception):
        send.send(payload)
    send.close()


def _elapsed(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _run(kind: ProbeKind, db_type: str, conn_params: dict[str, Any], timeout: float) -> dict[str, Any]:
    ctx = multiprocessing.get_context("spawn")
    receive, send = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_child, args=(send, kind, db_type, conn_params), daemon=True)
    start = time.monotonic()
    process.start()
    send.close()
    deadline = start + timeout
    try:
        # Sondeo corto: si el hijo muere sin responder (p. ej. un driver nativo que aborta), no se espera al timeout.
        while time.monotonic() < deadline:
            if receive.poll(0.1):
                result: dict[str, Any] = receive.recv()
                return result
            if not process.is_alive() and not receive.poll(0):
                return {"ok": False, "error": ("unknown", "ProcessDied"), "duration_ms": _elapsed(start)}
        return {"ok": False, "error": ("timeout", "TimeoutError"), "duration_ms": _elapsed(start)}
    except EOFError:
        return {"ok": False, "error": ("unknown", "ProcessDied"), "duration_ms": _elapsed(start)}
    finally:
        receive.close()
        process.join(0.5)
        if process.is_alive():
            process.kill()
            process.join(2)


def _error(payload: dict[str, Any]) -> ProbeError | None:
    if payload.get("ok"):
        return None
    code, exc_type = payload.get("error", ("unknown", "Unknown"))
    return ProbeError(code=code, exc_type=exc_type)


def check_connection(db_type: str, conn_params: dict[str, Any], *, timeout: float) -> ConnectionCheck:
    """Conecta con ``SyncDatabaseManager(db_type, conn_params, use_pool=False)`` y lee la versión del servidor."""
    payload = _run("test", db_type, conn_params, timeout)
    return ConnectionCheck(
        ok=bool(payload.get("ok")),
        duration_ms=int(payload.get("duration_ms", 0)),
        server_version=payload.get("server_version"),
        error=_error(payload),
    )


def engine_readiness(db_type: str, conn_params: dict[str, Any], *, timeout: float) -> ReadinessResult:
    """``SyncDatabaseManager.get_engine_readiness()`` en el subproceso."""
    payload = _run("readiness", db_type, conn_params, timeout)
    return ReadinessResult(
        supported=bool(payload.get("supported", False)),
        dynamic=bool(payload.get("dynamic", False)),
        detail=payload.get("detail"),
        checked_at=payload.get("checked_at"),
        findings=tuple(ReadinessFinding(*f) for f in payload.get("findings", [])),
        error=_error(payload),
    )
