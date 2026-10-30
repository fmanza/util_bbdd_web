"""Administración del almacenamiento (ADR-012): ajustes, vista previa de lo que se purgaría, «Aplicar ahora», uso por
usuario y «Mi espacio». Los permisos (admin o el propio usuario) los comprueba quien llama.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AppSetting, Run, Upload, User, utcnow
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.runs.service import retention_candidates
from app.domain.storage.purge import select_for_quota
from app.domain.storage.settings import (
    MAINTENANCE_KEY,
    STORAGE_KEYS,
    QuotaSource,
    defaults,
    effective_settings,
    overrides,
    quota_bytes,
    quota_source,
)
from app.domain.uploads.service import retention_candidates as upload_candidates


@dataclass(frozen=True)
class SettingState:
    """Valor efectivo de un ajuste, el de su variable ``UBW_*`` y si un admin lo cambió."""

    value: Any
    default: Any
    overridden: bool


def settings_state(db: Session, settings: Settings) -> dict[str, SettingState]:
    """Estado de cada ajuste administrable."""
    stored = overrides(db)
    base = defaults(settings)
    return {
        key: SettingState(value=stored.get(key, base[key]), default=base[key], overridden=key in stored)
        for key in STORAGE_KEYS
    }


def update_settings(
    db: Session, admin: User, changes: dict[str, Any], *, settings: Settings, ctx: RequestContext
) -> dict[str, SettingState]:
    """Guarda los ajustes de ``changes`` (``None`` = volver a la variable ``UBW_*``) y audita los que cambian."""
    before = settings_state(db, settings)
    for key, value in changes.items():
        row = db.get(AppSetting, key)
        if value is None:
            if row is not None:
                db.delete(row)
        elif row is None:
            db.add(AppSetting(key=key, value=value, updated_by=admin.id))
        else:
            row.value, row.updated_by = value, admin.id
    db.flush()
    after = settings_state(db, settings)
    diff = {
        key: {"from": before[key].value, "to": after[key].value}
        for key in changes
        if (before[key].value, before[key].overridden) != (after[key].value, after[key].overridden)
    }
    if diff:
        audit.record(
            db, action=AuditAction.STORAGE_UPDATE, ctx=ctx, actor_id=admin.id, target_type="storage",
            details={"changes": diff},
        )  # fmt: skip
    db.commit()
    return after


@dataclass(frozen=True)
class PurgePreview:
    """Lo que purgaría la siguiente pasada del mantenimiento con unos ajustes (sin borrar nada)."""

    runs: int
    run_bytes: int
    uploads: int
    upload_bytes: int
    users: int


def preview(db: Session, settings: Settings, proposed: dict[str, Any], *, now: datetime | None = None) -> PurgePreview:
    """Retención de ejecuciones y de ficheros y, si está activa, purga por cuota tras la retención."""
    effective = effective_settings(db, settings, proposed)
    runs = {run.id: run for run in retention_candidates(db, effective, now=now)}
    uploads = upload_candidates(db, effective, now=now)
    freed: dict[int, int] = {}
    for run in runs.values():
        if run.user_id is not None:
            freed[run.user_id] = freed.get(run.user_id, 0) + run.size_bytes
    for upload in uploads:
        if upload.user_id is not None:
            freed[upload.user_id] = freed.get(upload.user_id, 0) + upload.size_bytes
    if effective.quota_purge:
        owners = db.scalars(select(Run.user_id).where(Run.status != "purged", Run.user_id.is_not(None)).distinct())
        for user_id in owners.all():
            user = db.get(User, user_id)
            if user is None:
                continue
            for run in select_for_quota(
                db, user, effective, freed=freed.get(user.id, 0), exclude=frozenset(runs), now=now
            ):
                runs[run.id] = run
    affected = {r.user_id for r in runs.values()} | {u.user_id for u in uploads}
    return PurgePreview(
        runs=len(runs),
        run_bytes=sum(r.size_bytes for r in runs.values()),
        uploads=len(uploads),
        upload_bytes=sum(u.size_bytes for u in uploads),
        users=len(affected - {None}),
    )


def request_maintenance(db: Session, admin: User, *, ctx: RequestContext) -> None:
    """Pide al worker que aplique ya la retención y la purga por cuota (lo recoge en su siguiente ciclo)."""
    row = db.get(AppSetting, MAINTENANCE_KEY)
    stamp = utcnow().isoformat()
    if row is None:
        db.add(AppSetting(key=MAINTENANCE_KEY, value=stamp, updated_by=admin.id))
    else:
        row.value, row.updated_by = stamp, admin.id
    audit.record(db, action=AuditAction.STORAGE_MAINTENANCE, ctx=ctx, actor_id=admin.id, target_type="storage")
    db.commit()


@dataclass(frozen=True)
class Usage:
    """Espacio de un usuario frente a su cuota."""

    user_id: int
    username: str
    display_name: str
    run_bytes: int
    upload_bytes: int
    quota_bytes: int | None
    quota_source: QuotaSource

    @property
    def used_bytes(self) -> int:
        return self.run_bytes + self.upload_bytes

    @property
    def used_pct(self) -> float | None:
        return round(100 * self.used_bytes / self.quota_bytes, 1) if self.quota_bytes else None


def _usage(user: User, effective: Settings, runs: dict[int, int], uploads: dict[int, int]) -> Usage:
    return Usage(
        user_id=user.id, username=user.username, display_name=user.display_name, run_bytes=runs.get(user.id, 0),
        upload_bytes=uploads.get(user.id, 0), quota_bytes=quota_bytes(user, effective),
        quota_source=quota_source(user, effective),
    )  # fmt: skip


def _bytes_by_user(db: Session, user_ids: list[int] | None = None) -> tuple[dict[int, int], dict[int, int]]:
    run_query = select(Run.user_id, func.sum(Run.size_bytes)).where(Run.status != "purged").group_by(Run.user_id)
    upload_query = select(Upload.user_id, func.sum(Upload.size_bytes)).group_by(Upload.user_id)
    if user_ids is not None:
        run_query = run_query.where(Run.user_id.in_(user_ids))
        upload_query = upload_query.where(Upload.user_id.in_(user_ids))
    runs = {int(uid): int(total or 0) for uid, total in db.execute(run_query) if uid is not None}
    uploads = {int(uid): int(total or 0) for uid, total in db.execute(upload_query) if uid is not None}
    return runs, uploads


def usage_page(db: Session, settings: Settings, *, q: str | None, limit: int, offset: int) -> tuple[list[Usage], int]:
    """Uso por usuario, de más a menos espacio (con ``q``, solo usuarios cuyo nombre lo contiene)."""
    effective = effective_settings(db, settings)
    query = select(User)
    if q:
        pattern = f"%{q.strip().lower()}%"
        query = query.where(func.lower(User.username).like(pattern) | func.lower(User.display_name).like(pattern))
    users = db.scalars(query).all()
    runs, uploads = _bytes_by_user(db)
    items = sorted((_usage(u, effective, runs, uploads) for u in users), key=lambda u: (-u.used_bytes, u.username))
    return items[offset : offset + limit], len(items)


@dataclass(frozen=True)
class MyStorage:
    """«Mi espacio»: el uso del usuario de la sesión y si le afecta la purga por cuota."""

    usage: Usage
    quota_purge: bool
    quota_purge_target_pct: int
    upload_max_mb: int


def my_storage(db: Session, user: User, settings: Settings) -> MyStorage:
    effective = effective_settings(db, settings)
    runs, uploads = _bytes_by_user(db, [user.id])
    return MyStorage(
        usage=_usage(user, effective, runs, uploads),
        quota_purge=effective.quota_purge,
        quota_purge_target_pct=effective.quota_purge_target_pct,
        upload_max_mb=effective.upload_max_mb,
    )
