"""Errores de dominio de identidad, convertidos en *problem details* por ``app.core.errors``."""

from __future__ import annotations

from app.core.errors import AppError


class InvalidCredentialsError(AppError):
    """Usuario inexistente, desactivado, bloqueado o contraseña incorrecta: mismo mensaje para no enumerar."""

    status = 401
    title = "Credenciales no válidas"

    def __init__(self) -> None:
        super().__init__("Usuario o contraseña incorrectos, o cuenta bloqueada temporalmente.")


class PasswordPolicyError(AppError):
    """La contraseña nueva no cumple la política."""

    title = "Contraseña no válida"


class WrongCurrentPasswordError(AppError):
    """La contraseña actual indicada al cambiarla no es correcta."""

    title = "Contraseña actual incorrecta"


class UserNotFoundError(AppError):
    """Usuario inexistente."""

    status = 404
    title = "Usuario no encontrado"


class SessionNotFoundError(AppError):
    """Sesión inexistente o ya caducada."""

    status = 404
    title = "Sesión no encontrada"


class UsernameTakenError(AppError):
    """Nombre de usuario ya registrado."""

    status = 409
    title = "El usuario ya existe"


class LastAdminError(AppError):
    """La operación dejaría el sistema sin administradores activos."""

    status = 409
    title = "Debe quedar al menos un administrador activo"


class RoleNotFoundError(AppError):
    """El rol no existe."""

    status = 404
    title = "Rol no encontrado"


class RoleNameTakenError(AppError):
    """Ya hay un rol con ese nombre (sin distinguir mayúsculas)."""

    status = 409
    title = "Ya existe un rol con ese nombre"


class RoleBuiltinError(AppError):
    """Los roles base no se borran ni cambian de permisos."""

    status = 409
    title = "Los roles base no se pueden cambiar ni borrar"


class RoleInUseError(AppError):
    """El rol tiene usuarios."""

    status = 409
    title = "El rol tiene usuarios"


class InvalidPermissionError(AppError):
    """Permisos que no están en el catálogo."""

    status = 422
    title = "Permiso desconocido"


class PermissionEscalationError(AppError):
    """Se intenta dar (o quitar) un permiso que no se tiene."""

    status = 403
    title = "No puedes conceder permisos que no tienes"


class SelfModificationError(AppError):
    """Un administrador no puede desactivarse ni quitarse el rol a sí mismo."""

    status = 409
    title = "No puedes desactivarte ni cambiar tu propio rol"


class SelfDeletionError(AppError):
    """Un administrador no puede eliminar su propia cuenta."""

    status = 409
    title = "No puedes eliminar tu propia cuenta"


class UserInUseError(AppError):
    """El usuario tiene proyectos o conexiones que dependen de él; ``extra`` lleva el detalle (``blockers``)."""

    status = 409
    title = "El usuario tiene proyectos o conexiones"


class TransferBlockedError(AppError):
    """La transferencia no se puede hacer; ``extra`` lleva el motivo y lo que se movería."""

    status = 409
    title = "No se puede transferir"
