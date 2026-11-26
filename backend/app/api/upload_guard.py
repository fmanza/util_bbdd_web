"""Rechazo temprano de las subidas de ficheros (carga bulk y plantillas): sesión, CSRF y ``Content-Length``.

FastAPI lee el multipart entero (a ``TMPDIR``) antes de resolver las dependencias del endpoint, así que sin este
middleware cualquiera podría escribir GB en disco antes de recibir el 401. Aquí se decide solo con las cabeceras, sin
llamar a ``receive``; el endpoint repite sus comprobaciones (membresía, rol, cuota, tamaño real y contenido).
"""

from __future__ import annotations

from typing import Final

from fastapi.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.deps import csrf_protect, current_session
from app.core.config import Settings, get_settings
from app.core.errors import AppError, problem
from app.core.middleware import UPLOAD_PATH
from app.db.session import new_session
from app.domain.storage.settings import effective_settings
from app.i18n import Msg

#: Margen sobre el tamaño máximo para la cabecera ``Content-Length`` (límites del multipart y otros campos).
MULTIPART_OVERHEAD: Final = 64 * 1024


class UploadGuard:
    """Responde 401, 403, 411 o 413 a un ``POST`` de subida sin leer su cuerpo."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return
        match = UPLOAD_PATH.match(str(scope.get("path", "")))
        if match is None:
            await self.app(scope, receive, send)
            return
        request = Request(scope)  # sin receive: solo cabeceras y cookies
        settings = get_settings()  # como las dependencias del endpoint
        try:
            max_mb = await run_in_threadpool(_check_session, request, settings, bulk=match.group(2) == "uploads")
            csrf_protect(request, settings)
        except AppError as exc:  # 401 sin sesión o 403 sin token CSRF, como en el endpoint
            detail = exc.detail.render() if exc.detail else None
            await problem(exc.status, exc.title.render(), detail, code=exc.error_code)(scope, receive, send)
            return
        declared = request.headers.get("content-length", "")
        if not declared.isdigit():
            response = problem(
                411,
                Msg("api.upload_length_required_title").render(),
                Msg("api.upload_length_required").render(),
                code="api.upload_length_required",
            )
        elif int(declared) > max_mb * 1024 * 1024 + MULTIPART_OVERHEAD:
            response = problem(
                413,
                Msg("api.upload_too_large_title").render(),
                Msg("api.upload_too_large", max_mb=max_mb).render(),
                code="api.upload_too_large",
            )
        else:
            await self.app(scope, receive, send)
            return
        await response(scope, receive, send)


def _check_session(request: Request, settings: Settings, *, bulk: bool) -> int:
    """Valida la sesión (``NotAuthenticatedError`` 401) y devuelve el tamaño máximo de la subida en MB."""
    with new_session() as db:
        current_session(request, db, settings)
        if bulk:
            return effective_settings(db, settings).upload_max_mb  # administrable (ADR-012)
        return settings.template_max_mb
