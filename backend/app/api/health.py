"""Comprobación de salud para Docker ``HEALTHCHECK`` y el frontend."""

from __future__ import annotations

from datetime import timedelta
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app import __version__
from app.db.session import get_engine, new_session, ping
from app.domain.runs.health import worker_alive
from app.integrations.util_bbdd import library_version

router = APIRouter(tags=["health"])


class HealthStatus(BaseModel):
    """Estado del servicio.

    Attributes:
        status: ``ok`` si ``config.db`` responde y util_bbdd está instalado; ``degraded`` si no.
        version: Versión de util_bbdd_web.
        util_bbdd_version: Versión instalada de util_bbdd.
        database: Estado de ``config.db``.
        worker: ``ok`` si algún worker ha dado señales en los últimos 60 s, ``stale`` si solo hay latidos viejos,
            ``absent`` si nunca ha arrancado ninguno. No afecta a ``status`` (la API funciona sin worker).
    """

    status: Literal["ok", "degraded"]
    version: str
    util_bbdd_version: str | None
    database: Literal["ok", "error"]
    worker: Literal["ok", "stale", "absent", "unknown"]


@router.get("/health", response_model=HealthStatus, summary="Estado del servicio")
def health() -> HealthStatus:
    """Devuelve el estado de ``config.db`` y las versiones de la aplicación y de util_bbdd."""
    db_ok = ping(get_engine())
    lib = library_version()
    worker: Literal["ok", "stale", "absent", "unknown"] = "unknown"
    if db_ok:
        try:
            with new_session() as db:
                alive = worker_alive(db, within=timedelta(seconds=60))
            worker = "absent" if alive is None else ("ok" if alive else "stale")
        except SQLAlchemyError:
            worker = "unknown"
    return HealthStatus(
        status="ok" if db_ok and lib else "degraded",
        version=__version__,
        util_bbdd_version=lib,
        database="ok" if db_ok else "error",
        worker=worker,
    )
