"""Errores de las plantillas de documento (ADR-011)."""

from __future__ import annotations

from app.core.errors import AppError


class TemplateNotFoundError(AppError):
    """No existe o no es visible para el usuario (otro proyecto)."""

    status = 404


class TemplateTooLargeError(AppError):
    status = 413


class TemplateTypeError(AppError):
    status = 415


class TemplateContentError(AppError):
    """El contenido no es una plantilla válida o no es seguro distribuirla."""

    status = 422


class TemplateConflictError(AppError):
    """Nombre repetido o límite de plantillas alcanzado."""

    status = 409


class TemplateInUseError(AppError):
    status = 409
