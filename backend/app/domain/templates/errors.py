"""Errores de las plantillas de documento (ADR-011)."""

from __future__ import annotations

from app.core.errors import AppError


class TemplateNotFoundError(AppError):
    """No existe o no es visible para el usuario (otro proyecto)."""

    status = 404
    title = "Plantilla no encontrada"


class TemplateTooLargeError(AppError):
    status = 413
    title = "La plantilla es demasiado grande"


class TemplateTypeError(AppError):
    status = 415
    title = "Solo se admiten plantillas .docx, .dotx, .xlsx y .xltx"


class TemplateContentError(AppError):
    """El contenido no es una plantilla válida o no es seguro distribuirla."""

    status = 422
    title = "La plantilla no es válida"


class TemplateConflictError(AppError):
    """Nombre repetido o límite de plantillas alcanzado."""

    status = 409
    title = "No se puede guardar la plantilla"


class TemplateInUseError(AppError):
    status = 409
    title = "La plantilla la usa una documentación en cola o en curso"
