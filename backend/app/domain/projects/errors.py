"""Errores de dominio de proyectos, miembros y conexiones del proyecto."""

from __future__ import annotations

from app.core.errors import AppError


class ProjectNotFoundError(AppError):
    """Proyecto inexistente o del que el usuario no es miembro (no se revela su existencia)."""

    status = 404


class ProjectForbiddenError(AppError):
    """El rol del usuario en el proyecto no permite la acción."""

    status = 403


class ProjectNameTakenError(AppError):
    status = 409


class ProjectBusyError(AppError):
    """Hay ejecuciones en cola o en curso."""

    status = 409


class MemberNotFoundError(AppError):
    status = 404


class MemberExistsError(AppError):
    status = 409


class LastOwnerError(AppError):
    status = 409


class ProjectConnectionNotFoundError(AppError):
    status = 404


class AliasTakenError(AppError):
    status = 409
