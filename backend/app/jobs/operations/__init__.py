"""Implementaciones de las operaciones del catálogo (``app.domain.runs.operations``), ejecutadas en el subproceso."""

from __future__ import annotations

from collections.abc import Callable

from app.jobs.context import JobContext
from app.jobs.operations import noop

IMPLEMENTATIONS: dict[str, Callable[[JobContext], None]] = {
    "noop": noop.run,
}
