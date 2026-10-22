"""Cola de jobs sobre la tabla ``runs`` (ADR-002, opción b): reclamación atómica con ``UPDATE … RETURNING``."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.db.models import Run, Worker, utcnow


def claim_next(db: Session, worker_id: str, *, now: datetime | None = None) -> str | None:
    """Pasa a ``running`` la ejecución en cola más antigua y devuelve su id (``None`` si no hay).

    Un único ``UPDATE`` con subconsulta y ``RETURNING``: con SQLite (un escritor) dos workers nunca reclaman el mismo
    run, y la condición ``status = 'queued'`` lo protege de una cancelación simultánea.
    """
    now = now or utcnow()
    oldest = select(Run.id).where(Run.status == "queued").order_by(Run.created_at, Run.id).limit(1).scalar_subquery()
    claimed = db.execute(
        update(Run)
        .where(Run.id == oldest, Run.status == "queued")
        .values(
            status="running",
            phase="preparing",
            worker_id=worker_id,
            started_at=now,
            heartbeat_at=now,
            progress_message=None,
            progress_pct=None,
        )
        .returning(Run.id)
    ).scalar_one_or_none()
    db.commit()
    return claimed


def heartbeat(db: Session, worker_id: str, run_ids: list[str], *, now: datetime | None = None) -> None:
    """Latido del worker y de sus runs en curso."""
    now = now or utcnow()
    db.execute(update(Worker).where(Worker.id == worker_id).values(heartbeat_at=now))
    if run_ids:
        db.execute(update(Run).where(Run.id.in_(run_ids), Run.status == "running").values(heartbeat_at=now))
    db.commit()


def cancel_requested(db: Session, run_ids: list[str]) -> list[str]:
    """Runs en curso de ``run_ids`` con cancelación pedida."""
    if not run_ids:
        return []
    return list(
        db.scalars(select(Run.id).where(Run.id.in_(run_ids), Run.status == "running", Run.cancel_requested.is_(True)))
    )


def register_worker(db: Session, worker_id: str, *, pid: int, hostname: str) -> None:
    db.merge(Worker(id=worker_id, pid=pid, hostname=hostname[:255], started_at=utcnow(), heartbeat_at=utcnow()))
    db.commit()


def unregister_worker(db: Session, worker_id: str) -> None:
    db.execute(delete(Worker).where(Worker.id == worker_id))
    db.commit()


def stale_running(
    db: Session, *, stale_after: timedelta, exclude_worker: str, now: datetime | None = None
) -> list[str]:
    """Runs en curso de otros workers sin latido reciente (huérfanos tras una caída o un reinicio)."""
    cutoff = (now or utcnow()) - stale_after
    return list(
        db.scalars(
            select(Run.id).where(
                Run.status == "running",
                (Run.worker_id.is_(None)) | (Run.worker_id != exclude_worker),
                (Run.heartbeat_at.is_(None)) | (Run.heartbeat_at < cutoff),
            )
        )
    )
