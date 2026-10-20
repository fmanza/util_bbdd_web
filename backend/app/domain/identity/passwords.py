"""Hash Argon2id de contraseñas (pwdlib) y política mínima (ADR-003)."""

from __future__ import annotations

import secrets
from functools import lru_cache

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.domain.identity.errors import PasswordPolicyError

MAX_PASSWORD_LENGTH = 128  # acota el coste de Argon2 ante entradas enormes

_HASHER = PasswordHash((Argon2Hasher(),))


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return _HASHER.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    """Hash Argon2id con sal aleatoria."""
    return _HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> tuple[bool, str | None]:
    """Verifica ``password``.

    Returns:
        ``(válida, hash_nuevo)``; ``hash_nuevo`` no es ``None`` si los parámetros de Argon2 han cambiado y conviene
        guardar el hash recalculado.
    """
    return _HASHER.verify_and_update(password, password_hash)


def burn_verification(password: str) -> None:
    """Verifica contra un hash ficticio para que un usuario inexistente tarde lo mismo que uno real."""
    _HASHER.verify(password, _dummy_hash())


def check_policy(password: str, *, username: str, min_length: int) -> None:
    """Valida la política de contraseñas.

    Raises:
        PasswordPolicyError: Longitud fuera de rango o igual al nombre de usuario.
    """
    if len(password) < min_length:
        raise PasswordPolicyError(f"La contraseña debe tener al menos {min_length} caracteres.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordPolicyError(f"La contraseña no puede superar {MAX_PASSWORD_LENGTH} caracteres.")
    if password.strip().lower() == username.strip().lower():
        raise PasswordPolicyError("La contraseña no puede coincidir con el nombre de usuario.")
