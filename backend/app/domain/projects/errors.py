"""Errores de dominio de proyectos, miembros y conexiones del proyecto."""

from __future__ import annotations

from app.core.errors import AppError


class ProjectNotFoundError(AppError):
    """Proyecto inexistente o del que el usuario no es miembro (no se revela su existencia)."""

    status = 404
    title = "Proyecto no encontrado"


class ProjectForbiddenError(AppError):
    """El rol del usuario en el proyecto no permite la acción."""

    status = 403
    title = "Tu rol en el proyecto no permite esta acción"


class ProjectNameTakenError(AppError):
    status = 409
    title = "Ya tienes un proyecto con ese nombre"


class ProjectBusyError(AppError):
    """Hay ejecuciones en cola o en curso."""

    status = 409
    title = "El proyecto tiene ejecuciones en cola o en curso"


class MemberNotFoundError(AppError):
    status = 404
    title = "Miembro no encontrado"


class MemberExistsError(AppError):
    status = 409
    title = "El usuario ya es miembro del proyecto"


class LastOwnerError(AppError):
    status = 409
    title = "El proyecto debe tener al menos un propietario"


class ProjectConnectionNotFoundError(AppError):
    status = 404
    title = "Conexión del proyecto no encontrada"


class AliasTakenError(AppError):
    status = 409
    title = "El alias ya está en uso en el proyecto"
