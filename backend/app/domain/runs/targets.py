"""Escrituras en una BD destino (ADR-008/009/010): una sola a la vez por destino (migración, volcado o carga)."""

from __future__ import annotations

from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import TERMINAL_STATUSES, Run

WRITE_OPERATIONS: Final = ("migrate_apply", "dump_apply", "bulk_apply")


def _target_alias(db: Session, run: Run) -> str | None:
    """Alias destino de una escritura: en el propio run (migración) o en su vista previa (volcado, carga)."""
    if run.operation == "migrate_apply":
        return str(run.params.get("target_connection"))
    preview = db.get(Run, run.params.get("preview_run")) if run.params.get("preview_run") else None
    return str(preview.params.get("target_connection")) if preview is not None else None


def active_write(db: Session, project_id: int, alias: str) -> str | None:
    """Operación de escritura en cola o en curso sobre ``alias`` en el proyecto (``None`` si no hay)."""
    runs = db.scalars(
        select(Run).where(
            Run.project_id == project_id,
            Run.operation.in_(WRITE_OPERATIONS),
            Run.status.not_in((*TERMINAL_STATUSES, "purged")),
        )
    ).all()
    return next((run.operation for run in runs if _target_alias(db, run) == alias), None)
