"""Errores de dominio de motores, conexiones y allowlist (*problem details* vía ``AppError``)."""

from __future__ import annotations

from app.core.errors import AppError


class EngineNotFoundError(AppError):
    """Motor no soportado por util_bbdd."""

    status = 404
    title = "Motor no encontrado"


class ConnectionNotFoundError(AppError):
    """Conexión inexistente o privada de otro usuario (no se revela su existencia)."""

    status = 404
    title = "Conexión no encontrada"


class ConnectionForbiddenError(AppError):
    """Conexión visible (compartida) que el usuario no puede modificar, o visibilidad ``shared`` sin ser admin."""

    status = 403
    title = "No puedes modificar esta conexión"


class ConnectionNameTakenError(AppError):
    """El usuario ya tiene una conexión con ese nombre."""

    status = 409
    title = "Ya tienes una conexión con ese nombre"


class ConnectionParamsError(AppError):
    """Parámetros de conexión no válidos; ``errors`` indica el campo como en los 422 de validación."""

    status = 422
    title = "Parámetros de conexión no válidos"

    def __init__(self, detail: str, *, field: str | None = None) -> None:
        loc = ["body", "params", field] if field else ["body", "params"]
        super().__init__(detail, errors=[{"loc": loc, "msg": detail, "type": "value_error"}])


class TooManyTestsError(AppError):
    """Hay demasiadas pruebas de conexión en curso."""

    status = 429
    title = "Demasiadas pruebas de conexión en curso"

    def __init__(self) -> None:
        super().__init__("Espera unos segundos y vuelve a intentarlo.")


class InvalidAllowlistPatternError(AppError):
    """Patrón de allowlist que no es ni CIDR ni nombre de host válido."""

    status = 422
    title = "Patrón de destino no válido"


class AllowlistEntryNotFoundError(AppError):
    """Entrada de allowlist inexistente."""

    status = 404
    title = "Destino no encontrado"


class AllowlistDuplicateError(AppError):
    """El patrón ya está en la allowlist."""

    status = 409
    title = "El destino ya está en la lista"
