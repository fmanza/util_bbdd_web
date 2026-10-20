"""``/api/v1/sessions``: sesiones activas y revocación (solo ``admin``)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, Context, CurrentSession, DbSession, SettingsDep
from app.api.v1.schemas import MAX_PAGE_SIZE, SessionOut, SessionPage
from app.domain.identity import auth, sessions

router = APIRouter(prefix="/sessions", tags=["sessions"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    403: {"description": "Sin rol de administrador o token CSRF no válido"},
}


@router.get("", response_model=SessionPage, summary="Listar sesiones activas", responses=_ERRORS)
def list_sessions(
    _: AdminUser,
    current: CurrentSession,
    db: DbSession,
    settings: SettingsDep,
    user_id: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SessionPage:
    """Sesiones vigentes, la actividad más reciente primero."""
    rows, total = sessions.list_sessions(db, settings, user_id=user_id, limit=limit, offset=offset)
    items = [
        SessionOut(
            id=s.id,
            user_id=s.user_id,
            username=s.user.username,
            created_at=s.created_at,
            last_seen_at=s.last_seen_at,
            expires_at=s.expires_at,
            ip=s.ip,
            user_agent=s.user_agent,
            current=s.id == current.id,
        )
        for s in rows
    ]
    return SessionPage(items=items, total=total)


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revocar sesión",
    responses={**_ERRORS, 404: {"description": "No existe"}},
)
def revoke_session(session_id: int, admin: AdminUser, db: DbSession, ctx: Context) -> None:
    """Cierra la sesión indicada de inmediato."""
    auth.revoke_session(db, session_id, actor=admin, ctx=ctx)
