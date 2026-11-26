"""Errores de las subidas de ficheros (Fase 9, ADR-010)."""

from __future__ import annotations

from app.core.errors import AppError


class UploadNotFoundError(AppError):
    status = 404


class UploadTooLargeError(AppError):
    status = 413


class UploadTypeError(AppError):
    status = 415


class UploadContentError(AppError):
    """El contenido no es lo que dice la extensión, o no se puede leer."""

    status = 422


class NoColumnsError(UploadContentError):
    """El fichero, o la hoja del Excel, no tiene columnas (p. ej. una hoja vacía)."""


class UploadInUseError(AppError):
    status = 409


class UploadQuotaError(AppError):
    status = 409
