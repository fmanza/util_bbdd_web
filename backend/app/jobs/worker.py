"""Proceso worker (ADR-002): reclama ejecuciones de la cola y lanza un subproceso por job.

Uso::

    python -m app.jobs.worker

El bucle reclama hasta ``UBW_WORKER_CONCURRENCY`` jobs, emite latidos, aplica cancelaciones y timeouts terminando el
subproceso, cierra como ``worker_crash`` los hijos que mueren sin estado final, recupera huérfanos de un worker
anterior y aplica la retención del workspace y la purga por cuota (al arrancar, cada hora y cuando un admin pulsa
«Aplicar ahora»), con los ajustes efectivos de ADR-012. Termina limpio con ``SIGTERM``/``SIGINT``:
los jobs en curso se terminan y quedan como ``interrupted``.
"""

from __future__ import annotations

import logging
import multiprocessing
import os
import signal
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from multiprocessing.process import BaseProcess
from typing import Final

from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.ulid import new_ulid
from app.db.models import Run, utcnow
from app.db.session import new_session
from app.domain.identity.audit import RequestContext
from app.domain.runs.service import apply_retention
from app.domain.storage.purge import purge_over_quota
from app.domain.storage.settings import effective_settings, maintenance_requested_since
from app.domain.uploads.service import purge_old_uploads
from app.jobs import queue
from app.jobs.runner import finalize_run, run_job

logger = logging.getLogger(__name__)

RETENTION_INTERVAL: Final = 3600.0
#: Origen de lo que audita el worker por su cuenta (purga por cuota).
WORKER_CONTEXT: Final = RequestContext(ip=None, user_agent="worker")
TERMINATE_GRACE: Final = 5.0
#: Operaciones que paran por sí mismas al pedir la cancelación (``util_bbdd.progress``, GAPS G1): el worker les deja
#: ``COOPERATIVE_CANCEL_GRACE`` segundos antes de terminar el subproceso (ADR-002).
COOPERATIVE_OPERATIONS: Final = frozenset({"documentation", "relationship_graph", "compare"})
COOPERATIVE_CANCEL_GRACE: Final = 60.0


@dataclass
class _Child:
    process: BaseProcess
    started: float
    operation: str = ""
    #: Cuándo vio el worker la cancelación de una operación cooperativa (``None``: aún no).
    cancel_seen: float | None = None


class Worker:
    """Bucle del worker; ``tick()`` hace una iteración (los tests lo llaman directamente)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.id = f"{socket.gethostname()}-{os.getpid()}-{new_ulid()[-6:]}"
        self.children: dict[str, _Child] = {}
        self._ctx = multiprocessing.get_context("spawn")
        self._last_retention = 0.0
        self._maintained_at: datetime | None = None

    @property
    def stale_after(self) -> timedelta:
        return timedelta(seconds=max(30.0, self.settings.worker_poll_seconds * 10))

    def start(self) -> None:
        with new_session() as db:
            queue.register_worker(db, self.id, pid=os.getpid(), hostname=socket.gethostname())
        self.recover_orphans()
        self.maintenance(force=True)
        logger.info("Worker iniciado", extra={"worker_id": self.id, "concurrency": self.settings.worker_concurrency})

    def recover_orphans(self) -> list[str]:
        with new_session() as db:
            orphans = queue.stale_running(db, stale_after=self.stale_after, exclude_worker=self.id)
        for run_id in orphans:
            finalize_run(
                run_id, "failed", error_code="interrupted", error_message="El worker se detuvo durante la ejecución."
            )
        if orphans:
            logger.warning("Ejecuciones huérfanas cerradas", extra={"runs": orphans})
        return orphans

    def maintenance(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_retention < RETENTION_INTERVAL and not self._requested():
            return
        self._last_retention = now
        self._maintained_at = utcnow()
        try:
            with new_session() as db:
                effective = effective_settings(db, self.settings)
                apply_retention(db, effective)
                purge_old_uploads(db, effective)
                purge_over_quota(db, effective, ctx=WORKER_CONTEXT)
        except Exception as exc:  # la retención nunca debe parar el worker
            logger.error("Fallo aplicando la retención", extra={"exc_type": type(exc).__name__})

    def _requested(self) -> bool:
        """Un admin pidió aplicar ya el mantenimiento («Aplicar ahora») después de la última pasada."""
        try:
            with new_session() as db:
                return maintenance_requested_since(db, self._maintained_at)
        except Exception as exc:  # leer la petición nunca debe parar el worker
            logger.error("Fallo leyendo la petición de mantenimiento", extra={"exc_type": type(exc).__name__})
            return False

    def _stop_child(self, run_id: str, status: str, code: str, message: str) -> None:
        child = self.children.pop(run_id)
        child.process.terminate()
        child.process.join(TERMINATE_GRACE)
        if child.process.is_alive():
            child.process.kill()
            child.process.join(TERMINATE_GRACE)
        finalize_run(run_id, status, error_code=code, error_message=message)
        logger.info("Job detenido", extra={"run_id": run_id, "status": status, "code": code})

    def reap(self) -> None:
        """Retira los hijos terminados; si murieron sin cerrar el run, lo cierra como ``worker_crash``."""
        for run_id, child in list(self.children.items()):
            if child.process.is_alive():
                continue
            child.process.join()
            del self.children[run_id]
            closed = finalize_run(
                run_id, "failed", error_code="worker_crash",
                error_message=f"El proceso del job terminó de forma inesperada (código {child.process.exitcode}).",
            )  # fmt: skip
            if closed:
                logger.warning("Job sin estado final", extra={"run_id": run_id, "exitcode": child.process.exitcode})

    def enforce(self) -> None:
        """Cancelaciones pedidas y timeouts."""
        with new_session() as db:
            to_cancel = queue.cancel_requested(db, list(self.children))
        now = time.monotonic()
        for run_id in to_cancel:
            child = self.children[run_id]
            if child.operation in COOPERATIVE_OPERATIONS:
                if child.cancel_seen is None:
                    child.cancel_seen = now
                    logger.info("Cancelación cooperativa pedida", extra={"run_id": run_id})
                if now - child.cancel_seen < COOPERATIVE_CANCEL_GRACE:
                    continue
            self._stop_child(run_id, "cancelled", "cancelled", "Cancelada por un usuario.")
        limit = self.settings.job_timeout_seconds
        for run_id, child in list(self.children.items()):
            if time.monotonic() - child.started > limit:
                self._stop_child(run_id, "failed", "job_timeout", f"Superó el tiempo máximo ({limit} s).")

    def claim(self) -> None:
        while len(self.children) < self.settings.worker_concurrency:
            with new_session() as db:
                run_id = queue.claim_next(db, self.id)
            if run_id is None:
                return
            with new_session() as db:
                operation = db.scalar(select(Run.operation).where(Run.id == run_id)) or ""
            process = self._ctx.Process(target=run_job, args=(run_id,), name=f"job-{run_id}")
            process.start()
            self.children[run_id] = _Child(process=process, started=time.monotonic(), operation=operation)
            logger.info("Job lanzado", extra={"run_id": run_id, "pid": process.pid})

    def tick(self) -> None:
        with new_session() as db:
            queue.heartbeat(db, self.id, list(self.children))
        self.reap()
        self.enforce()
        self.claim()
        self.maintenance()

    def shutdown(self) -> None:
        for run_id in list(self.children):
            self._stop_child(run_id, "failed", "interrupted", "El worker se detuvo durante la ejecución.")
        with new_session() as db:
            queue.unregister_worker(db, self.id)
        logger.info("Worker detenido", extra={"worker_id": self.id})

    def run_forever(self, stop: threading.Event) -> None:
        self.start()
        try:
            while not stop.is_set():
                self.tick()
                stop.wait(self.settings.worker_poll_seconds)
        finally:
            self.shutdown()


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    stop = threading.Event()

    def _handle(signum: int, _: object) -> None:
        logger.info("Señal recibida", extra={"signal": signal.Signals(signum).name})
        stop.set()

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)
    Worker(settings).run_forever(stop)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
