"""Contexto que recibe la implementación de una operación dentro del subproceso del job."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

from sqlalchemy import update

from app.core.config import Settings
from app.db.models import Run
from app.db.session import new_session
from app.domain.connections.service import ERROR_MESSAGES, prepare_connection
from app.domain.projects.service import get_project_connection
from app.integrations.util_bbdd import probe

Phase = Literal["preparing", "connecting", "running", "reporting"]

#: El progreso se escribe como mucho una vez por segundo y run (SQLite tiene un único escritor), salvo cambio de fase.
PROGRESS_INTERVAL: Final = 1.0


class JobError(Exception):
    """Fallo controlado de una operación: ``code`` estable y ``message`` para el usuario (sin datos sensibles)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class JobContext:
    """Datos y utilidades de un job en curso."""

    run_id: str
    project_id: int
    operation: str
    params: dict[str, Any]
    run_dir: Path
    settings: Settings
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("app.jobs.run"))
    _last_write: float = 0.0
    _last_phase: str | None = None

    def outputs(self, kind: str) -> Path:
        """Carpeta ``outputs/<kind>/`` del run."""
        path = self.run_dir / "outputs" / kind
        path.mkdir(parents=True, exist_ok=True)
        return path

    def progress(self, phase: Phase, message: str | None = None, pct: int | None = None) -> None:
        """Publica el progreso en ``runs`` (lo emite la API por SSE)."""
        now = time.monotonic()
        if phase == self._last_phase and now - self._last_write < PROGRESS_INTERVAL:
            return
        self._last_phase, self._last_write = phase, now
        with new_session() as db:
            db.execute(
                update(Run)
                .where(Run.id == self.run_id, Run.status == "running")
                .values(phase=phase, progress_message=(message or "")[:255] or None, progress_pct=pct)
            )
            db.commit()
        self.logger.info("Progreso", extra={"phase": phase, "progress": message, "pct": pct})

    def test_connection(self, alias: str) -> tuple[str, str | None]:
        """Prueba la conexión del proyecto con ``alias`` (allowlist incluida).

        Returns:
            ``(db_type, versión_del_servidor)``.

        Raises:
            JobError: Alias desconocido o la conexión falla (código saneado).
        """
        from app.db.models import Project

        with new_session() as db:
            project = db.get(Project, self.project_id)
            if project is None:
                raise JobError("invalid_params", "El proyecto ya no existe.")
            try:
                link = get_project_connection(db, project, alias)
            except Exception:
                raise JobError("invalid_params", f"El proyecto no tiene la conexión «{alias}».") from None
            connection = link.connection
            prepared = prepare_connection(db, connection, self.settings)
            db.commit()
        if prepared.conn_params is None:
            code = prepared.error_code or "unknown"
            raise JobError(code, ERROR_MESSAGES.get(code, ERROR_MESSAGES["unknown"]))
        result = probe.check_connection(
            connection.db_type, prepared.conn_params, timeout=self.settings.connection_test_timeout
        )
        if not result.ok:
            code = result.error.code if result.error else "unknown"
            self.logger.info(
                "Conexión fallida",
                extra={"alias": alias, "code": code, "exc_type": result.error and result.error.exc_type},
            )
            raise JobError(code, ERROR_MESSAGES.get(code, ERROR_MESSAGES["unknown"]))
        return connection.db_type, result.server_version
