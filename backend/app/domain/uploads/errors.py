"""Errores de las subidas de ficheros (Fase 9, ADR-010)."""

from __future__ import annotations

from app.core.errors import AppError


class UploadNotFoundError(AppError):
    status = 404
    title = "Fichero no encontrado"


class UploadTooLargeError(AppError):
    status = 413
    title = "El fichero es demasiado grande"


class UploadTypeError(AppError):
    status = 415
    title = "Solo se admiten ficheros .csv y .xlsx"


class UploadContentError(AppError):
    """El contenido no es lo que dice la extensión, o no se puede leer."""

    status = 422
    title = "El fichero no es válido"


class NoColumnsError(UploadContentError):
    """El fichero, o la hoja del Excel, no tiene columnas (p. ej. una hoja vacía)."""


class UploadInUseError(AppError):
    status = 409
    title = "El fichero lo usa una carga en curso"


class UploadQuotaError(AppError):
    status = 409
    title = "Cuota de almacenamiento superada"
