"""Errores del explorador de metadatos, las queries nombradas y el SQL libre."""

from __future__ import annotations

from app.core.errors import AppError
from app.domain.connections.service import ERROR_MESSAGES
from app.i18n import Msg

EXTRA_MESSAGES: dict[str, Msg] = {
    "query_error": Msg("explorer.query_error"),
    "not_read_only": Msg("explorer.not_read_only"),
}


def message_for(code: str) -> Msg:
    return EXTRA_MESSAGES.get(code) or ERROR_MESSAGES.get(code, ERROR_MESSAGES["unknown"])


class DatabaseAccessError(AppError):
    """No se pudo leer de la BD destino; ``reason`` (el ``code`` de la respuesta) es estable y el detalle nunca lleva
    texto del driver."""

    status = 502

    def __init__(self, *, reason: str, detail: Msg | None = None) -> None:
        super().__init__(detail or message_for(reason))
        self.reason = reason

    @property
    def error_code(self) -> str:
        return self.reason


class DatabaseTimeoutError(DatabaseAccessError):
    status = 504


class ObjectNotFoundError(AppError):
    status = 404


class SqlNotAllowedError(AppError):
    """El usuario no tiene el permiso de SQL libre."""

    status = 403


class ConnectionNotReadOnlyError(AppError):
    status = 409


class SqlRejectedError(AppError):
    """El SQL no pasa el guardián de solo lectura o el motor lo rechaza (con su mensaje recortado)."""

    status = 422

    def __init__(self, detail: Msg, *, reason: str) -> None:
        super().__init__(detail)
        self.reason = reason

    @property
    def error_code(self) -> str:
        return self.reason


class NamedQueryNotFoundError(AppError):
    status = 404


class NamedQueryNameTakenError(AppError):
    status = 409


class NamedQueryInvalidError(AppError):
    status = 422
