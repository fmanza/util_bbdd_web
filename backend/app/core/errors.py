"""Errores de la API en formato *problem details* (RFC 9457), en el idioma de la petición (ADR-015).

Los mensajes que llegan al cliente nunca incluyen el texto de excepciones de drivers: pueden contener la URL de
conexión con la contraseña. El detalle va al log, saneado (ver ``security.instructions.md``).

Cada respuesta lleva ``code``, estable e independiente del idioma: la clave del ``detail`` (``runs.preview_expired``)
o, sin detalle, el ``code`` de la clase (``connection_not_found``). Los errores por campo (``errors``) llevan también el
suyo, para que un cliente pueda sustituir un texto concreto sin depender de él.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from typing import Any, ClassVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_context import current_request_id
from app.i18n import Msg, current_lang, has_key, translate

PROBLEM_JSON = "application/problem+json"

logger = logging.getLogger(__name__)

_CAMEL = re.compile(r"(?<!^)(?=[A-Z])")


def _default_code(name: str) -> str:
    """``ConnectionNotFoundError`` → ``connection_not_found``."""
    return _CAMEL.sub("_", name.removesuffix("Error")).lower()


class AppError(Exception):
    """Error de negocio con estado HTTP; las capas de dominio lo especializan sin depender de FastAPI.

    Una subclase solo declara ``status``: su ``code`` sale del nombre de la clase y su título es la clave
    ``title.<code>`` del catálogo (``app/i18n/catalog/``); ambos se pueden fijar explícitamente.

    Attributes:
        status: Código HTTP de la respuesta.
        code: Código estable de la clase (``code`` del *problem details* cuando no hay ``detail``).
        title: Título del *problem details*.
        detail: Explicación para el usuario (nunca texto de excepciones de terceros).
        extra: Campos adicionales del *problem details* (p. ej. ``errors`` por campo, ver :func:`field_error`).
    """

    status: ClassVar[int] = 400
    code: ClassVar[str] = "app"
    title: ClassVar[Msg] = Msg("title.app")

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if "code" not in cls.__dict__:
            cls.code = _default_code(cls.__name__)
        if "title" not in cls.__dict__:
            cls.title = Msg(f"title.{cls.code}")

    def __init__(self, detail: Msg | None = None, **extra: object) -> None:
        super().__init__(detail.key if detail else self.code)
        self.detail = detail
        self.extra = extra

    @property
    def error_code(self) -> str:
        """``code`` de la respuesta: el del detalle si lo hay, si no el de la clase."""
        return self.detail.key if self.detail else self.code


def field_error(field: str | Sequence[str | int], msg: Msg, type_: str = "value_error") -> dict[str, object]:
    """Entrada de ``errors`` (mismo formato que los 422 de validación); ``field`` sin ``loc`` completa va en ``body``."""
    loc = ["body", field] if isinstance(field, str) else list(field)
    return {"loc": loc, "msg": msg, "type": type_}


def _render(value: object) -> object:
    """Compone los :class:`Msg` de los campos extra (también dentro de listas y diccionarios)."""
    if isinstance(value, Msg):
        return value.render()
    if isinstance(value, dict):
        rendered = {k: _render(v) for k, v in value.items()}
        if isinstance(value.get("msg"), Msg) and "code" not in value:
            rendered["code"] = value["msg"].key
        return rendered
    if isinstance(value, list | tuple):
        return [_render(v) for v in value]
    return value


def problem(status: int, title: str, detail: str | None = None, *, code: str, **extra: object) -> JSONResponse:
    """Respuesta ``application/problem+json`` con ``code`` y el ``request_id`` de la petición (para soporte)."""
    body: dict[str, object] = {"type": "about:blank", "title": title, "status": status, "code": code}
    if detail:
        body["detail"] = detail
    body.update({k: _render(v) for k, v in extra.items()})
    if (request_id := current_request_id()) is not None:
        body["request_id"] = request_id
    response = JSONResponse(body, status_code=status, media_type=PROBLEM_JSON)
    response.headers["Content-Language"] = current_lang()
    response.headers["Vary"] = "Accept-Language"
    return response


def http_title(status: int) -> str:
    key = f"http.{status}"
    return (
        translate(key, current_lang()) if has_key(key) else translate("http.other", current_lang(), {"status": status})
    )


def _validation_message(error: Any) -> str:
    """Mensaje de un error de Pydantic en el idioma de la petición; sin traducción, el original de Pydantic.

    Los validadores propios lanzan ``PydanticCustomError`` con una clave del catálogo como ``type``.
    """
    kind = str(error.get("type", ""))
    ctx = {k: _ctx_value(v) for k, v in (error.get("ctx") or {}).items()}
    for key in (kind, f"validation.{kind}"):
        if has_key(key):
            return translate(key, current_lang(), ctx)
    return str(error.get("msg", ""))


def _ctx_value(value: object) -> object:
    return value if isinstance(value, str | int | float | bool) else str(value)


def install_error_handlers(app: FastAPI) -> None:
    """Registra los handlers que convierten cualquier error en *problem details*."""

    @app.exception_handler(AppError)
    async def _app(_: Request, exc: AppError) -> JSONResponse:
        detail = exc.detail.render() if exc.detail else None
        response = problem(exc.status, exc.title.render(), detail, code=exc.error_code, **exc.extra)
        if (retry_after := getattr(exc, "retry_after", None)) is not None:
            response.headers["Retry-After"] = str(retry_after)
        return response

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Solo lo lanzan Starlette y FastAPI (ruta inexistente, método no permitido…): su ``detail`` es un texto en
        # inglés sin interés para el usuario. El código propio usa siempre ``AppError``.
        return problem(exc.status_code, http_title(exc.status_code), code=f"http_{exc.status_code}")

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": list(e["loc"]), "msg": _validation_message(e), "type": e["type"], "code": e["type"]}
            for e in exc.errors()
        ]
        return problem(422, translate("title.validation", current_lang()), code="validation_error", errors=errors)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Error no controlado", extra={"path": request.url.path, "exc_type": type(exc).__name__})
        return problem(500, translate("title.internal", current_lang()), code="internal")
