"""Errores de dominio de ejecuciones y artefactos."""

from __future__ import annotations

from app.core.errors import AppError


class RunNotFoundError(AppError):
    """Ejecución inexistente o de un proyecto del que el usuario no es miembro."""

    status = 404
    title = "Ejecución no encontrada"


class ArtifactNotFoundError(AppError):
    status = 404
    title = "Artefacto no encontrado"


class UnknownOperationError(AppError):
    status = 422
    title = "Operación desconocida"


class RunParamsError(AppError):
    """Parámetros de la operación no válidos (``errors`` por campo)."""

    status = 422
    title = "Parámetros de la ejecución no válidos"


class RunStateError(AppError):
    """La ejecución no está en un estado que permita la acción."""

    status = 409
    title = "La ejecución no admite esta acción en su estado actual"


class QuotaExceededError(AppError):
    status = 409
    title = "Cuota de almacenamiento superada"


class TooManyRunsError(AppError):
    status = 429
    title = "Demasiadas ejecuciones en cola"
