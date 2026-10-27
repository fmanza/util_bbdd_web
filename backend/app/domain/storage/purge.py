"""Purga por cuota (ADR-012): opcional (``quota_purge``), desactivada por defecto.

Cuando el espacio de un usuario llega a su cuota, se purgan **sus** ejecuciones terminadas, de la más antigua a la más
reciente, hasta bajar al ``quota_purge_target_pct`` de la cuota. Nunca se purgan las terminadas hace menos de
``PROTECTED_AGE`` (vistas previas y modos secos que aún sirven, resultados recién generados) ni las que cita una
ejecución en cola o en curso (vista previa, plan o modo seco). Purgar conserva la fila y su ``run.json`` (``purged``).
Se aplica al encolar, al subir un fichero y en el mantenimiento del worker; los ficheros subidos y las plantillas
siguen con su propia retención.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import TERMINAL_STATUSES, Run, User, utcnow
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.runs.service import ACTIVE_STATUSES, dump_journal, purge_run, usage_bytes
from app.domain.storage.settings import quota_bytes

logger = logging.getLogger(__name__)

PROTECTED_AGE: Final = timedelta(minutes=60)
#: Parámetros con los que una ejecución cita otra (vista previa, plan y modo seco).
_LINKS: Final = ("preview_run", "plan_run", "dry_run_run")


def _referenced(db: Session) -> set[str]:
    """Ejecuciones citadas por una en cola o en curso."""
    active = db.scalars(select(Run).where(Run.status.in_(ACTIVE_STATUSES))).all()
    return {str(run.params[key]) for run in active for key in _LINKS if run.params.get(key)}


def _purgeable(db: Session, user_id: int, now: datetime) -> list[Run]:
    """Ejecuciones de ``user_id`` que se pueden purgar por cuota, de la más antigua a la más reciente."""
    query = (
        select(Run)
        .where(
            Run.user_id == user_id,
            Run.status.in_(tuple(TERMINAL_STATUSES)),
            Run.size_bytes > 0,
            Run.finished_at < now - PROTECTED_AGE,
        )
        .order_by(Run.finished_at, Run.id)
    )
    protected = _referenced(db)
    return [run for run in db.scalars(query).all() if run.id not in protected]


def select_for_quota(
    db: Session,
    user: User,
    settings: Settings,
    *,
    incoming: int = 0,
    freed: int = 0,
    exclude: frozenset[str] = frozenset(),
    now: datetime | None = None,
) -> list[Run]:
    """Ejecuciones que la purga por cuota borraría (sin borrar nada).

    Args:
        settings: Ajustes **efectivos**.
        incoming: Bytes que van a entrar (un fichero subido).
        freed: Bytes que ya se liberan por otra vía (la retención, en la vista previa del admin).
        exclude: Ejecuciones que ya se purgan por otra vía.
    """
    quota = quota_bytes(user, settings)
    if not settings.quota_purge or quota is None:
        return []
    used = usage_bytes(db, user.id) + incoming - freed
    if used < quota:
        return []
    target = quota * settings.quota_purge_target_pct // 100
    chosen: list[Run] = []
    for run in _purgeable(db, user.id, now or utcnow()):
        if used <= target:
            break
        if run.id in exclude or dump_journal(run, settings) is not None:  # constraints sin restaurar (G31)
            continue
        chosen.append(run)
        used -= run.size_bytes
    return chosen


def purge_for_quota(
    db: Session, user: User, settings: Settings, *, ctx: RequestContext, incoming: int = 0, now: datetime | None = None
) -> int:
    """Purga lo que elija ``select_for_quota``, lo audita (``run.purge`` con ``reason=quota``) y confirma."""
    runs = select_for_quota(db, user, settings, incoming=incoming, now=now)
    for run in runs:
        size = run.size_bytes
        purge_run(db, run, settings)
        audit.record(
            db, action=AuditAction.RUN_PURGE, ctx=ctx, actor_id=None, target_type="run", target_id=run.id,
            details={"reason": "quota", "user_id": user.id, "size_bytes": size},
        )  # fmt: skip
    if runs:
        db.commit()
        logger.info("Purga por cuota", extra={"user_id": user.id, "purged": len(runs)})
    return len(runs)


def purge_over_quota(db: Session, settings: Settings, *, ctx: RequestContext, now: datetime | None = None) -> int:
    """Mantenimiento del worker: purga por cuota a cada usuario con ejecuciones que ocupan espacio."""
    if not settings.quota_purge:
        return 0
    owners = db.scalars(
        select(Run.user_id).where(Run.status != "purged", Run.size_bytes > 0, Run.user_id.is_not(None)).distinct()
    ).all()
    total = 0
    for user_id in owners:
        user = db.get(User, user_id)
        if user is not None:
            total += purge_for_quota(db, user, settings, ctx=ctx, now=now)
    return total
