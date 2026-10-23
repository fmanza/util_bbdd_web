"""``GET /metrics`` en formato Prometheus (Fase 10).

Desactivado salvo que exista ``UBW_METRICS_TOKEN`` (Docker secret ``ubw_metrics_token``): responde 404 sin token
configurado y 401 sin el *bearer* correcto. Las métricas no llevan usuarios, proyectos ni identificadores: las rutas
van por plantilla y las ejecuciones se cuentan por estado y operación al hacer *scrape*.
"""

from __future__ import annotations

import hmac
import logging
from collections.abc import Iterator
from datetime import timedelta

from fastapi import APIRouter, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app import __version__
from app.core.config import get_settings
from app.core.errors import problem
from app.db.models import Run, Worker, utcnow
from app.db.session import new_session
from app.integrations.util_bbdd import library_version

logger = logging.getLogger(__name__)

router = APIRouter(include_in_schema=False)


class RunsCollector(Collector):
    """Ejecuciones por estado y operación, y latido del worker más reciente, leídos de ``config.db``."""

    def describe(self) -> list[GaugeMetricFamily]:
        """Vacío: sin él, el registro llamaría a :meth:`collect` (consulta a la BD) al registrarlo."""
        return []

    def collect(self) -> Iterator[GaugeMetricFamily]:
        info = GaugeMetricFamily("ubw_info", "Versiones de util_bbdd_web y util_bbdd.", labels=["version", "util_bbdd"])
        info.add_metric([__version__, library_version() or "missing"], 1)
        yield info
        runs = GaugeMetricFamily("ubw_runs", "Ejecuciones por estado y operación.", labels=["status", "operation"])
        heartbeat = GaugeMetricFamily(
            "ubw_worker_heartbeat_age_seconds", "Segundos desde el último latido de un worker (-1 sin worker)."
        )
        try:
            with new_session() as db:
                rows = db.execute(select(Run.status, Run.operation, func.count()).group_by(Run.status, Run.operation))
                for status, operation, count in rows:
                    runs.add_metric([status, operation], count)
                last = db.scalar(select(func.max(Worker.heartbeat_at)))
            heartbeat.add_metric([], (utcnow() - last) / timedelta(seconds=1) if last else -1)
        except SQLAlchemyError:
            logger.warning("Métricas de ejecuciones no disponibles")
            return
        yield runs
        yield heartbeat


def register_collectors(registry: CollectorRegistry) -> None:
    registry.register(RunsCollector())


@router.get("/metrics", response_model=None)
def metrics(request: Request) -> Response:
    """Métricas en formato de texto de Prometheus."""
    token = get_settings().metrics_token
    if token is None:
        return problem(404, "Not Found")
    expected = f"Bearer {token.get_secret_value()}".encode()
    if not hmac.compare_digest(request.headers.get("Authorization", "").encode(), expected):
        response = problem(401, "No autenticado")
        response.headers["WWW-Authenticate"] = "Bearer"
        return response
    registry: CollectorRegistry = request.app.state.http_metrics.registry
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
