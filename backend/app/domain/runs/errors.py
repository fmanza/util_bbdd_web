"""Errores de dominio de ejecuciones y artefactos."""

from __future__ import annotations

from app.core.errors import AppError


class RunNotFoundError(AppError):
    """Ejecución inexistente o de un proyecto del que el usuario no es miembro."""

    status = 404


class ArtifactNotFoundError(AppError):
    status = 404


class UnknownOperationError(AppError):
    status = 422


class RunParamsError(AppError):
    """Parámetros de la operación no válidos (``errors`` por campo)."""

    status = 422


class RunStateError(AppError):
    """La ejecución no está en un estado que permita la acción."""

    status = 409


class QuotaExceededError(AppError):
    status = 409


class TooManyRunsError(AppError):
    status = 429


class DiffNotAvailableError(AppError):
    """La ejecución no es una comparación terminada con su diff (o se purgó)."""

    status = 404


class DiffTooLargeError(AppError):
    status = 413
