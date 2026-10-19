"""Errores de la API en formato *problem details* (RFC 9457).

Los mensajes que llegan al cliente nunca incluyen el texto de excepciones de drivers: pueden contener la URL de
conexión con la contraseña. El detalle va al log, saneado (ver ``security.instructions.md``).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_JSON = "application/problem+json"

logger = logging.getLogger(__name__)


def problem(status: int, title: str, detail: str | None = None, **extra: object) -> JSONResponse:
    """Respuesta ``application/problem+json``."""
    body: dict[str, object] = {"type": "about:blank", "title": title, "status": status}
    if detail:
        body["detail"] = detail
    body.update(extra)
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON)


def install_error_handlers(app: FastAPI) -> None:
    """Registra los handlers que convierten cualquier error en *problem details*."""

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem(exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return problem(422, "Datos de entrada no válidos", errors=errors)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Error no controlado", extra={"path": request.url.path, "exc_type": type(exc).__name__})
        return problem(500, "Error interno")
