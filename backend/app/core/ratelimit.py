"""Limitador de peticiones en memoria por ventana deslizante (Fase 10).

Vale para un único proceso de la API (el ``web`` de Docker Compose es un solo uvicorn). Con varios procesos cada uno
lleva su cuenta: el límite efectivo se multiplica (documentado en la guía de despliegue).
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from app.core.errors import AppError

_SWEEP_EVERY: Final = 1000  # comprobaciones entre limpiezas de claves inactivas


class RateLimitedError(AppError):
    status = 429
    title = "Demasiadas peticiones"

    def __init__(self, retry_after: int) -> None:
        super().__init__(f"Espera {retry_after} s antes de reintentar.", code="rate_limited")
        self.retry_after = retry_after


@dataclass(frozen=True)
class Limit:
    """``limit`` eventos como máximo en ``window`` segundos."""

    limit: int
    window: float


class SlidingWindowLimiter:
    """Cuenta eventos por clave en una ventana deslizante; seguro entre hilos (rutas síncronas en el threadpool)."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._checks = 0

    def hit(self, key: str, rule: Limit) -> int | None:
        """Registra un evento. Devuelve ``None`` si cabe o los segundos hasta que quepa otro (sin registrarlo)."""
        now = self._clock()
        with self._lock:
            self._maybe_sweep(now, rule.window)
            events = self._events.setdefault(key, deque())
            while events and events[0] <= now - rule.window:
                events.popleft()
            if len(events) >= rule.limit:
                return max(1, math.ceil(events[0] + rule.window - now))
            events.append(now)
            return None

    def blocked(self, key: str, rule: Limit) -> int | None:
        """Como :meth:`hit` pero sin registrar: segundos de espera si la clave ya agotó el límite."""
        now = self._clock()
        with self._lock:
            events = self._events.get(key)
            if not events:
                return None
            while events and events[0] <= now - rule.window:
                events.popleft()
            if len(events) >= rule.limit:
                return max(1, math.ceil(events[0] + rule.window - now))
            return None

    def record(self, key: str) -> None:
        """Registra un evento sin comprobar (p. ej. un login fallido, que se limita con :meth:`blocked`)."""
        with self._lock:
            self._events.setdefault(key, deque()).append(self._clock())

    def _maybe_sweep(self, now: float, window: float) -> None:
        self._checks += 1
        if self._checks % _SWEEP_EVERY:
            return
        horizon = now - max(window, 3600.0)
        for key in [k for k, v in self._events.items() if not v or v[-1] <= horizon]:
            del self._events[key]
