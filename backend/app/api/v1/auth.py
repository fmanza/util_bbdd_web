"""``/api/v1/auth``: inicio y cierre de sesión, usuario actual, «Mi espacio» (ADR-012) y cambio de contraseña (ADR-003)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response, status

from app.api.deps import (
    Context,
    CurrentSession,
    DbSession,
    SettingsDep,
    clear_auth_cookies,
    session_cookie,
    set_auth_cookies,
    set_csrf_cookie,
)
from app.api.v1.schemas import CsrfToken, LoginRequest, Me, PasswordChange
from app.api.v1.schemas_storage import MyStorageOut
from app.core.errors import AppError
from app.core.middleware import client_ip
from app.core.ratelimit import Limit, RateLimitedError, SlidingWindowLimiter
from app.core.security import new_csrf_token, session_csrf_token
from app.domain.identity import auth
from app.domain.storage.service import my_storage

router = APIRouter(prefix="/auth", tags=["auth"])

_401: dict[int | str, dict[str, Any]] = {401: {"description": "No autenticado"}}
_403: dict[int | str, dict[str, Any]] = {403: {"description": "Token CSRF ausente o no válido"}}
_429: dict[int | str, dict[str, Any]] = {429: {"description": "Demasiados intentos desde esta IP (``Retry-After``)"}}
_FAILURE_WINDOW = 15 * 60


@router.get("/csrf", response_model=CsrfToken, summary="Obtener token CSRF")
def get_csrf(request: Request, response: Response, settings: SettingsDep) -> CsrfToken:
    """Devuelve el token CSRF y lo pone en la cookie ``ubw_csrf``.

    Sin sesión es aleatorio (protege el propio login); con cookie de sesión es el ligado a ella.
    """
    session_token = request.cookies.get(session_cookie(settings))
    token = session_csrf_token(settings, session_token) if session_token else new_csrf_token()
    set_csrf_cookie(response, settings, token)
    return CsrfToken(csrf_token=token)


@router.post(
    "/login",
    response_model=Me,
    summary="Iniciar sesión",
    responses={401: {"description": "Credenciales no válidas o cuenta bloqueada"}, **_403, **_429},
)
def login(
    body: LoginRequest, request: Request, response: Response, db: DbSession, settings: SettingsDep, ctx: Context
) -> Me:
    """Autentica, rota la sesión y pone las cookies ``ubw_session`` y ``ubw_csrf``.

    Además del bloqueo por cuenta (ADR-003), limita por IP los intentos por minuto y los fallidos en 15 minutos: así
    no se puede probar una contraseña contra muchas cuentas ni bloquearlas todas desde un mismo origen.
    """
    limiter: SlidingWindowLimiter = request.app.state.limiter
    ip = client_ip(request.scope)
    failures = Limit(settings.rate_limit_login_failures, _FAILURE_WINDOW)
    if settings.rate_limit_enabled:
        wait = limiter.blocked(f"login-fail:{ip}", failures) or limiter.hit(
            f"login:{ip}", Limit(settings.rate_limit_login_per_minute, 60)
        )
        if wait is not None:
            raise RateLimitedError(wait)
    try:
        issued = auth.login(
            db,
            username=body.username,
            password=body.password.get_secret_value(),
            settings=settings,
            ctx=ctx,
            previous_token=request.cookies.get(session_cookie(settings)),
        )
    except AppError as exc:
        if exc.status == 401 and settings.rate_limit_enabled:
            limiter.record(f"login-fail:{ip}")
        raise
    set_auth_cookies(response, settings, issued.token)
    return Me.model_validate(issued.session.user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Cerrar sesión", responses={**_401, **_403})
def logout(session: CurrentSession, response: Response, db: DbSession, settings: SettingsDep, ctx: Context) -> None:
    """Borra la sesión actual y sus cookies."""
    auth.logout(db, session, ctx=ctx)
    clear_auth_cookies(response, settings)


@router.get("/me", response_model=Me, summary="Usuario actual", responses=_401)
def me(session: CurrentSession) -> Me:
    """Usuario de la sesión actual."""
    return Me.model_validate(session.user)


@router.get("/me/storage", response_model=MyStorageOut, summary="Mi espacio", responses=_401)
def me_storage(session: CurrentSession, db: DbSession, settings: SettingsDep) -> MyStorageOut:
    """Espacio del usuario de la sesión frente a su cuota (solo cantidades)."""
    mine = my_storage(db, session.user, settings)
    usage = mine.usage
    return MyStorageOut(
        run_bytes=usage.run_bytes, upload_bytes=usage.upload_bytes, used_bytes=usage.used_bytes,
        quota_bytes=usage.quota_bytes, quota_source=usage.quota_source, used_pct=usage.used_pct,
        quota_purge=mine.quota_purge, quota_purge_target_pct=mine.quota_purge_target_pct,
    )  # fmt: skip


@router.post(
    "/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cambiar mi contraseña",
    responses={400: {"description": "Contraseña actual incorrecta o nueva no válida"}, **_401, **_403},
)
def change_password(
    body: PasswordChange, session: CurrentSession, db: DbSession, settings: SettingsDep, ctx: Context
) -> None:
    """Cambia la contraseña y cierra las demás sesiones del usuario."""
    auth.change_password(
        db,
        session,
        current_password=body.current_password.get_secret_value(),
        new_password=body.new_password.get_secret_value(),
        settings=settings,
        ctx=ctx,
    )
