"""``RunAuditSink``: destino de ``util_bbdd.audit`` que escribe en ``logs/run.log`` de la ejecución (ADR-005).

Implementa el protocolo ``util_bbdd.audit.AuditSink`` (``write(events)`` atómico por llamada y seguro entre hilos,
``close()`` idempotente, ``write`` tras ``close`` lanza ``ValueError``). Descarta ``AuditEvent.message``: util_bbdd
documenta que puede contener valores de clave (``IntegrityError``) y el log del run lo ven todos los miembros.
"""

from __future__ import annotations

import json
import threading
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from util_bbdd.audit import AuditEvent


class RunAuditSink:
    """Añade cada ``AuditEvent`` como una línea JSON (``"logger": "util_bbdd.audit"``) al log del run."""

    def __init__(self, log_path: Path) -> None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._path = log_path
        self._lock = threading.Lock()
        self._closed = False
        self.counts: Counter[str] = Counter()

    def write(self, events: Sequence[AuditEvent], /) -> None:
        if not events:
            with self._lock:
                if self._closed:
                    raise ValueError("RunAuditSink cerrado")
            return
        lines = []
        for event in events:
            data: dict[str, Any] = dict(event.as_dict())
            data.pop("message", None)
            lines.append(json.dumps({"logger": "util_bbdd.audit", **data}, ensure_ascii=False, default=str))
        text = "\n".join(lines) + "\n"
        with self._lock:
            if self._closed:
                raise ValueError("RunAuditSink cerrado")
            with self._path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
            self.counts.update(event.status for event in events)

    def close(self) -> None:
        with self._lock:
            self._closed = True
