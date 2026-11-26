"""Errores de dominio de motores, conexiones y allowlist (*problem details* vía ``AppError``)."""

from __future__ import annotations

from app.core.errors import AppError, field_error
from app.i18n import Msg


class EngineNotFoundError(AppError):
    """Motor no soportado por util_bbdd."""

    status = 404


class ConnectionNotFoundError(AppError):
    """Conexión inexistente o privada de otro usuario (no se revela su existencia)."""

    status = 404


class ConnectionForbiddenError(AppError):
    """Conexión visible (compartida) que el usuario no puede modificar, o visibilidad ``shared`` sin ser admin."""

    status = 403


class ConnectionNameTakenError(AppError):
    """El usuario ya tiene una conexión con ese nombre."""

    status = 409


class ConnectionParamsError(AppError):
    """Parámetros de conexión no válidos; ``errors`` indica el campo como en los 422 de validación."""

    status = 422

    def __init__(self, detail: Msg, *, field: str | None = None) -> None:
        loc = ["body", "params", field] if field else ["body", "params"]
        super().__init__(detail, errors=[field_error(loc, detail)])


class TooManyTestsError(AppError):
    """Hay demasiadas pruebas de conexión en curso."""

    status = 429

    def __init__(self) -> None:
        super().__init__(Msg("connections.too_many_tests"))


class InvalidAllowlistPatternError(AppError):
    """Patrón de allowlist que no es ni CIDR ni nombre de host válido."""

    status = 422


class AllowlistEntryNotFoundError(AppError):
    """Entrada de allowlist inexistente."""

    status = 404


class AllowlistDuplicateError(AppError):
    """El patrón ya está en la allowlist."""

    status = 409
