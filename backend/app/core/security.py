"""Primitivas criptográficas de sesión y CSRF (ADR-003), sin estado ni dependencias de dominio."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from app.core.config import Settings

SESSION_TOKEN_BYTES = 32  # 256 bits
CSRF_TOKEN_BYTES = 32

# Clave efímera por proceso para development/test cuando no hay ``UBW_APP_SECRET_KEY``; en producción
# ``create_app`` exige la clave (ver ``require_secret_key``).
_EPHEMERAL_KEY = secrets.token_bytes(32)


class MissingSecretKeyError(RuntimeError):
    """Falta un secreto obligatorio en producción (``UBW_APP_SECRET_KEY`` o ``UBW_FERNET_KEYS``)."""


def require_secret_key(settings: Settings) -> None:
    """Falla al arrancar si producción no tiene clave de firma ni claves Fernet (ADR-003, ADR-004)."""
    if settings.environment != "production":
        return
    if settings.app_secret_key is None:
        raise MissingSecretKeyError("UBW_APP_SECRET_KEY (secret ubw_app_secret_key) es obligatoria en producción")
    if settings.fernet_keys is None or not settings.fernet_keys.get_secret_value().strip():
        raise MissingSecretKeyError("UBW_FERNET_KEYS (secret ubw_fernet_keys) es obligatoria en producción")


def _signing_key(settings: Settings) -> bytes:
    if settings.app_secret_key is None:
        return _EPHEMERAL_KEY
    return settings.app_secret_key.get_secret_value().encode("utf-8")


def new_session_token() -> str:
    """Token de sesión aleatorio de 256 bits (solo viaja en la cookie; en BD se guarda su hash)."""
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def new_csrf_token() -> str:
    """Token CSRF anónimo para el doble envío previo al inicio de sesión."""
    return secrets.token_urlsafe(CSRF_TOKEN_BYTES)


def hash_token(token: str) -> str:
    """SHA-256 hexadecimal del token de sesión (lo único que se persiste)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_csrf_token(settings: Settings, session_token: str) -> str:
    """Token CSRF ligado a la sesión: ``HMAC-SHA256(clave, token_de_sesión)``.

    Una cookie ``ubw_csrf`` inyectada desde otro origen no sirve sin conocer la clave y el token de sesión.
    """
    return hmac.new(_signing_key(settings), session_token.encode("utf-8"), hashlib.sha256).hexdigest()


def tokens_match(a: str, b: str) -> bool:
    """Comparación en tiempo constante."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def site_token(settings: Settings, *, run_id: str, user_id: int, expires: int) -> str:
    """Token de la URL del sitio HTML de un run: ``<user_id>.<expires>.<HMAC>`` (ADR-007).

    El ``iframe`` del sitio tiene origen opaco y sus subrecursos no llevan la cookie ``SameSite=Lax``; la URL firmada
    sustituye a la cookie solo para leer ese sitio, y en cada petición se vuelve a comprobar la membresía.
    """
    message = f"site:{run_id}:{user_id}:{expires}".encode()
    signature = hmac.new(_signing_key(settings), message, hashlib.sha256).hexdigest()[:40]
    return f"{user_id}.{expires}.{signature}"


def verify_site_token(settings: Settings, token: str, *, run_id: str, now: int) -> int | None:
    """``user_id`` del token si la firma es válida y no ha caducado; ``None`` en otro caso."""
    parts = token.split(".")
    if len(parts) != 3 or not parts[0].isdigit() or not parts[1].isdigit():
        return None
    user_id, expires = int(parts[0]), int(parts[1])
    if expires < now:
        return None
    expected = site_token(settings, run_id=run_id, user_id=user_id, expires=expires)
    return user_id if tokens_match(expected, token) else None
