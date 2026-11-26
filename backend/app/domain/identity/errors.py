"""Errores de dominio de identidad, convertidos en *problem details* por ``app.core.errors``."""

from __future__ import annotations

from app.core.errors import AppError
from app.i18n import Msg


class InvalidCredentialsError(AppError):
    """Usuario inexistente, desactivado, bloqueado o contraseña incorrecta: mismo mensaje para no enumerar."""

    status = 401

    def __init__(self) -> None:
        super().__init__(Msg("identity.invalid_credentials"))


class PasswordPolicyError(AppError):
    """La contraseña nueva no cumple la política."""


class WrongCurrentPasswordError(AppError):
    """La contraseña actual indicada al cambiarla no es correcta."""


class UserNotFoundError(AppError):
    """Usuario inexistente."""

    status = 404


class SessionNotFoundError(AppError):
    """Sesión inexistente o ya caducada."""

    status = 404


class UsernameTakenError(AppError):
    """Nombre de usuario ya registrado."""

    status = 409


class LastAdminError(AppError):
    """La operación dejaría el sistema sin administradores activos."""

    status = 409


class RoleNotFoundError(AppError):
    """El rol no existe."""

    status = 404


class RoleNameTakenError(AppError):
    """Ya hay un rol con ese nombre (sin distinguir mayúsculas)."""

    status = 409


class RoleBuiltinError(AppError):
    """Los roles base no se borran ni cambian de permisos."""

    status = 409


class RoleInUseError(AppError):
    """El rol tiene usuarios."""

    status = 409


class InvalidPermissionError(AppError):
    """Permisos que no están en el catálogo."""

    status = 422


class PermissionEscalationError(AppError):
    """Se intenta dar (o quitar) un permiso que no se tiene."""

    status = 403


class SelfModificationError(AppError):
    """Un administrador no puede desactivarse ni quitarse el rol a sí mismo."""

    status = 409


class SelfDeletionError(AppError):
    """Un administrador no puede eliminar su propia cuenta."""

    status = 409


class UserInUseError(AppError):
    """El usuario tiene proyectos o conexiones que dependen de él; ``extra`` lleva el detalle (``blockers``)."""

    status = 409


class TransferBlockedError(AppError):
    """La transferencia no se puede hacer; ``extra`` lleva el motivo y lo que se movería."""

    status = 409
