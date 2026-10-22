"""Ejecución de una tarea de util_bbdd en un subproceso con timeout (ADR-002).

Un driver colgado no bloquea la API: el hijo (*spawn*) se mata al vencer el timeout. Los argumentos (con los
``conn_params`` y la contraseña) viajan por la tubería de ``multiprocessing``, nunca por argv ni por el entorno. El hijo
desactiva el logging y la salida estándar, porque util_bbdd y los drivers pueden escribir la URL de conexión.

Al padre solo vuelve el resultado de la tarea (tipos simples) o un error saneado: un código, el tipo de la excepción
y, únicamente si la excepción es ``PublicError``, un mensaje que la tarea ha decidido mostrar.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import logging
import multiprocessing
import sys
import time
from dataclasses import dataclass
from multiprocessing.connection import Connection
from typing import Any, Literal

ErrorCode = Literal[
    "driver_missing", "invalid_config", "connection_failed", "timeout", "query_error", "not_read_only", "unknown"
]


class PublicError(Exception):
    """Error cuyo ``code`` y ``message`` puede ver el usuario (la tarea garantiza que no llevan secretos)."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class TaskError:
    """Error de la tarea: ``code`` para el usuario, ``exc_type`` solo para el log y ``message`` si es público."""

    code: ErrorCode
    exc_type: str
    message: str | None = None


@dataclass(frozen=True)
class TaskResult:
    """Resultado de :func:`run_isolated`."""

    value: Any
    error: TaskError | None
    duration_ms: int

    @property
    def ok(self) -> bool:
        return self.error is None


def classify(exc: BaseException) -> ErrorCode:
    """Código estable a partir del tipo de excepción (nunca de su mensaje)."""
    from util_bbdd import exceptions as e

    if isinstance(exc, PublicError):
        return exc.code
    if isinstance(exc, e.DriverError | ImportError | ModuleNotFoundError):
        return "driver_missing"
    if isinstance(exc, e.QueryTimeoutError | e.PoolTimeoutError | TimeoutError):
        return "timeout"
    if isinstance(exc, e.ValidationError | e.InvalidConnectionConfig | ValueError | TypeError | KeyError):
        return "invalid_config"
    if isinstance(exc, e.ConnectionError | e.PoolConnectionError | e.DatabaseConfigurationError | OSError):
        return "connection_failed"
    return "unknown"


def _child(send: Connection, target: str, kwargs: dict[str, Any]) -> None:
    logging.disable(logging.CRITICAL)
    sys.stdout = sys.stderr = io.StringIO()
    payload: dict[str, Any]
    try:
        module_name, function_name = target.split(":")
        function = getattr(importlib.import_module(module_name), function_name)
        payload = {"ok": True, "value": function(**kwargs)}
    except BaseException as exc:  # frontera del proceso: todo se reduce a un código (y un mensaje si es público)
        message = exc.message if isinstance(exc, PublicError) else None
        payload = {"ok": False, "error": (classify(exc), type(exc).__name__, message)}
    with contextlib.suppress(Exception):
        send.send(payload)
    send.close()


def _elapsed(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def run_isolated(target: str, kwargs: dict[str, Any], *, timeout: float) -> TaskResult:
    """Ejecuta ``módulo:función(**kwargs)`` en un subproceso *spawn* y espera como mucho ``timeout`` segundos.

    La función debe ser importable a nivel de módulo y devolver tipos que se puedan enviar por la tubería.
    """
    ctx = multiprocessing.get_context("spawn")
    receive, send = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_child, args=(send, target, kwargs), daemon=True)
    start = time.monotonic()
    process.start()
    send.close()
    deadline = start + timeout
    try:
        # Sondeo corto: si el hijo muere sin responder (p. ej. un driver nativo que aborta), no se espera al timeout.
        while time.monotonic() < deadline:
            if receive.poll(0.1):
                payload: dict[str, Any] = receive.recv()
                if payload.get("ok"):
                    return TaskResult(value=payload.get("value"), error=None, duration_ms=_elapsed(start))
                code, exc_type, message = payload.get("error", ("unknown", "Unknown", None))
                return TaskResult(value=None, error=TaskError(code, exc_type, message), duration_ms=_elapsed(start))
            if not process.is_alive() and not receive.poll(0):
                return TaskResult(None, TaskError("unknown", "ProcessDied"), _elapsed(start))
        return TaskResult(None, TaskError("timeout", "TimeoutError"), _elapsed(start))
    except EOFError:
        return TaskResult(None, TaskError("unknown", "ProcessDied"), _elapsed(start))
    finally:
        receive.close()
        process.join(0.5)
        if process.is_alive():
            process.kill()
            process.join(2)
