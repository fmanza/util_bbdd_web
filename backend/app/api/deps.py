"""Dependencias comunes de los routers: BD, ajustes, sesión actual, permisos del rol (ADR-014) y CSRF (ADR-003)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import session_csrf_token, tokens_match
from app.db.models import User, UserSession
from app.db.session import get_session
from app.domain.identity.audit import RequestContext
from app.domain.identity.permissions import Permission
from app.domain.identity.sessions import resolve_session

SESSION_COOKIE = "ubw_session"
CSRF_COOKIE = "ubw_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


def session_cookie(settings: Settings) -> str:
    """Nombre de la cookie de sesión: ``__Host-ubw_session`` con TLS, ``ubw_session`` en ``development``."""
    return settings.cookie_prefix + SESSION_COOKIE


def csrf_cookie(settings: Settings) -> str:
    """Nombre de la cookie CSRF: ``__Host-ubw_csrf`` con TLS, ``ubw_csrf`` en ``development``."""
    return settings.cookie_prefix + CSRF_COOKIE


DbSession = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def request_context(request: Request) -> RequestContext:
    """IP y ``User-Agent`` de la petición."""
    return RequestContext(
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


Context = Annotated[RequestContext, Depends(request_context)]


class NotAuthenticatedError(AppError):
    """Sin cookie de sesión o con una sesión caducada o revocada."""

    status = 401


class PermissionDeniedError(AppError):
    """El rol del usuario no tiene ninguno de los permisos que exige la ruta (ADR-014)."""

    status = 403


class InvalidCsrfTokenError(AppError):
    """Falta la cabecera ``X-CSRF-Token`` o no coincide con la cookie y la sesión."""

    status = 403


def current_session(request: Request, db: DbSession, settings: SettingsDep) -> UserSession:
    """Sesión válida de la cookie ``ubw_session``.

    Raises:
        NotAuthenticatedError: 401 si no hay cookie o la sesión no es válida.
    """
    token = request.cookies.get(session_cookie(settings))
    session = resolve_session(db, token, settings) if token else None
    if session is None:
        raise NotAuthenticatedError()
    return session


CurrentSession = Annotated[UserSession, Depends(current_session)]


def current_user(session: CurrentSession) -> User:
    """Usuario de la sesión actual."""
    return session.user


CurrentUser = Annotated[User, Depends(current_user)]


def require_permission(*permissions: Permission) -> Callable[[User], User]:
    """Dependencia: usuario actual cuyo rol tiene **alguno** de ``permissions`` (ADR-014).

    Raises:
        PermissionDeniedError: 403 si no tiene ninguno.
    """

    def dependency(user: CurrentUser) -> User:
        if not any(user.can(permission) for permission in permissions):
            raise PermissionDeniedError()
        return user

    return dependency


UserManager = Annotated[User, Depends(require_permission("users.manage"))]
RoleManager = Annotated[User, Depends(require_permission("roles.manage"))]
#: Ver los roles: quien los gestiona y quien asigna roles a usuarios.
RoleReader = Annotated[User, Depends(require_permission("roles.manage", "users.manage"))]
SessionManager = Annotated[User, Depends(require_permission("sessions.manage"))]
AuditReader = Annotated[User, Depends(require_permission("audit.read"))]
TemplateManager = Annotated[User, Depends(require_permission("templates.manage"))]
QueryManager = Annotated[User, Depends(require_permission("queries.manage"))]
AllowlistManager = Annotated[User, Depends(require_permission("allowlist.manage"))]
StorageManager = Annotated[User, Depends(require_permission("storage.manage"))]
RunsAdmin = Annotated[User, Depends(require_permission("runs.admin"))]


def csrf_protect(request: Request, settings: SettingsDep) -> None:
    """Doble envío firmado en métodos no seguros.

    La cabecera ``X-CSRF-Token`` debe coincidir con la cookie ``ubw_csrf``; con sesión, además, con
    ``HMAC(clave, token_de_sesión)``.

    Raises:
        InvalidCsrfTokenError: 403 si falta o no coincide.
    """
    if request.method in SAFE_METHODS:
        return
    header = request.headers.get(CSRF_HEADER, "")
    cookie = request.cookies.get(csrf_cookie(settings), "")
    if not header or not cookie or not tokens_match(header, cookie):
        raise InvalidCsrfTokenError()
    session_token = request.cookies.get(session_cookie(settings))
    if session_token and not tokens_match(header, session_csrf_token(settings, session_token)):
        raise InvalidCsrfTokenError()


def set_auth_cookies(response: Response, settings: Settings, session_token: str) -> str:
    """Pone ``ubw_session`` (``HttpOnly``) y ``ubw_csrf`` (legible por la SPA); devuelve el token CSRF."""
    max_age = settings.session_absolute_hours * 3600
    csrf = session_csrf_token(settings, session_token)
    response.set_cookie(
        session_cookie(settings),
        session_token,
        max_age=max_age,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    set_csrf_cookie(response, settings, csrf, max_age=max_age)
    return csrf


def set_csrf_cookie(response: Response, settings: Settings, token: str, *, max_age: int | None = None) -> None:
    """Cookie ``ubw_csrf`` sin ``HttpOnly`` para que la SPA la copie en la cabecera."""
    response.set_cookie(
        csrf_cookie(settings),
        token,
        max_age=max_age,
        path="/",
        secure=settings.cookie_secure,
        httponly=False,
        samesite="lax",
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    """Borra las cookies de sesión y CSRF."""
    for name, httponly in ((session_cookie(settings), True), (csrf_cookie(settings), False)):
        response.delete_cookie(name, path="/", secure=settings.cookie_secure, httponly=httponly, samesite="lax")
