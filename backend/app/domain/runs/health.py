"""Estado del worker para ``/api/health`` (la API no importa ``app.jobs``)."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Worker, utcnow


def worker_alive(db: Session, *, within: timedelta, now: datetime | None = None) -> bool | None:
    """``True`` si algún worker tiene latido reciente; ``False`` si solo hay latidos viejos; ``None`` si ninguno."""
    beats = list(db.scalars(select(Worker.heartbeat_at)))
    if not beats:
        return None
    cutoff = (now or utcnow()) - within
    return any(beat >= cutoff for beat in beats)
