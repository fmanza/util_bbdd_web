"""Puente entre el progreso y la cancelación de util_bbdd (``util_bbdd.progress``, 4.1.0) y los del run (GAPS G1).

util_bbdd emite un ``ProgressEvent`` por fase y por unidad de trabajo (tabla, formato…) y comprueba un
``CancellationToken`` entre unidades. ``RunProgress`` es el ``on_progress`` que se le pasa: traduce cada evento a
``ctx.progress`` (mensaje y porcentaje del run) y, como mucho cada ``poll_seconds``, pregunta si se pidió cancelar el run
para cancelar el token. Así la parada es cooperativa: util_bbdd termina la unidad en curso, deja el destino coherente y
lanza ``OperationCancelledError``. El worker solo mata el subproceso si no para a tiempo (ADR-002).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any


class RunProgress:
    """``on_progress`` para util_bbdd con su ``CancellationToken`` (``token``).

    Args:
        report: Publica ``(mensaje, porcentaje)`` en el run (``lambda m, p: ctx.progress("running", m, p)``).
        cancel_requested: Si se pidió cancelar el run (lee la base de datos de la web).
        phases: Fases de la operación en orden; el porcentaje se reparte a partes iguales entre ellas.
        labels: Texto de cada fase para el mensaje (por defecto, el nombre de la fase).
        poll_seconds: Intervalo mínimo entre dos lecturas de ``cancel_requested``.
    """

    def __init__(
        self,
        report: Callable[[str, int | None], None],
        cancel_requested: Callable[[], bool],
        phases: Sequence[str],
        labels: Mapping[str, str] | None = None,
        *,
        poll_seconds: float = 2.0,
    ) -> None:
        from util_bbdd.progress import CancellationToken

        self.token = CancellationToken()
        self._report = report
        self._cancel_requested = cancel_requested
        self._phases = list(phases)
        self._labels = dict(labels or {})
        self._poll_seconds = poll_seconds
        self._polled_at: float | None = None

    def __call__(self, event: Any) -> None:
        self._report(self.message(event), self.percent(event))
        self._poll()

    def percent(self, event: Any) -> int | None:
        """Porcentaje del run: fases terminadas más la parte hecha de la actual."""
        if event.phase not in self._phases:
            return None
        done = self._phases.index(event.phase) + (event.fraction or 0.0)
        return min(99, int(done * 100 / len(self._phases)))

    def message(self, event: Any) -> str:
        label = str(self._labels.get(event.phase, event.phase))
        if event.total:
            text = f"{label}: {event.current} de {event.total}"
            return f"{text} ({event.message})" if event.message else text
        return label

    def _poll(self) -> None:
        if self.token.is_cancelled():
            return
        now = time.monotonic()
        if self._polled_at is not None and now - self._polled_at < self._poll_seconds:
            return
        self._polled_at = now
        if self._cancel_requested():
            self.token.cancel()


def is_cancellation(exc: BaseException) -> bool:
    """Si ``exc`` (o su causa) es la parada cooperativa de util_bbdd (``OperationCancelledError``)."""
    from util_bbdd.exceptions import OperationCancelledError

    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        if isinstance(current, OperationCancelledError):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False
