"""Errores del explorador de metadatos, las queries nombradas y el SQL libre."""

from __future__ import annotations

from app.core.errors import AppError
from app.domain.connections.service import ERROR_MESSAGES

EXTRA_MESSAGES: dict[str, str] = {
    "query_error": "El motor rechazó la consulta.",
    "not_read_only": "Solo se admiten consultas de lectura.",
}


def message_for(code: str) -> str:
    return EXTRA_MESSAGES.get(code) or ERROR_MESSAGES.get(code, ERROR_MESSAGES["unknown"])


class DatabaseAccessError(AppError):
    """No se pudo leer de la BD destino; ``code`` es estable y el detalle nunca lleva texto del driver."""

    status = 502
    title = "No se pudo consultar la base de datos"

    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or message_for(code), code=code)
        self.code = code


class DatabaseTimeoutError(DatabaseAccessError):
    status = 504
    title = "La base de datos no respondió a tiempo"


class ObjectNotFoundError(AppError):
    status = 404
    title = "Objeto no encontrado en el schema"


class SqlNotAllowedError(AppError):
    """El usuario no tiene el permiso de SQL libre."""

    status = 403
    title = "No tienes permiso para ejecutar SQL libre"


class ConnectionNotReadOnlyError(AppError):
    status = 409
    title = "El SQL libre solo se permite sobre conexiones de solo lectura"


class SqlRejectedError(AppError):
    """El SQL no pasa el guardián de solo lectura o el motor lo rechaza (con su mensaje recortado)."""

    status = 422
    title = "Consulta no admitida"

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail, code=code)


class NamedQueryNotFoundError(AppError):
    status = 404
    title = "Query no encontrada"


class NamedQueryNameTakenError(AppError):
    status = 409
    title = "Ya existe una query con ese nombre para el motor"


class NamedQueryInvalidError(AppError):
    status = 422
    title = "Query no válida"
