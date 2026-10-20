"""Cifrado de los secretos de conexión con MultiFernet (ADR-004)."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import Settings

logger = logging.getLogger(__name__)

# Clave efímera por proceso para development/test sin ``UBW_FERNET_KEYS`` (los secretos no sobreviven a un
# reinicio). En producción ``create_app`` exige las claves.
_EPHEMERAL_KEY = Fernet.generate_key().decode("ascii")


class SecretDecryptError(RuntimeError):
    """Ninguna de las claves configuradas descifra el secreto (clave retirada o datos corruptos)."""


class SecretBox:
    """Cifra y descifra ``dict`` de secretos. La primera clave cifra; todas descifran (rotación)."""

    def __init__(self, keys: list[str]) -> None:
        if not keys:
            raise ValueError("Se necesita al menos una clave Fernet")
        self._fernet = MultiFernet([Fernet(key.encode("ascii")) for key in keys])

    def encrypt(self, secrets: dict[str, Any]) -> str:
        return self._fernet.encrypt(json.dumps(secrets, separators=(",", ":")).encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> dict[str, Any]:
        try:
            data: dict[str, Any] = json.loads(self._fernet.decrypt(token.encode("ascii")))
        except InvalidToken:
            raise SecretDecryptError("No se puede descifrar el secreto con las claves configuradas") from None
        return data

    def rotate(self, token: str) -> str:
        """Vuelve a cifrar ``token`` con la clave principal."""
        try:
            return self._fernet.rotate(token.encode("ascii")).decode("ascii")
        except InvalidToken:
            raise SecretDecryptError("No se puede descifrar el secreto con las claves configuradas") from None


def parse_keys(raw: str) -> list[str]:
    """Claves separadas por comas (la primera cifra)."""
    return [key.strip() for key in raw.split(",") if key.strip()]


@lru_cache(maxsize=4)
def _box(raw_keys: str) -> SecretBox:
    return SecretBox(parse_keys(raw_keys))


def secret_box(settings: Settings) -> SecretBox:
    """``SecretBox`` de las claves de ``UBW_FERNET_KEYS`` o, fuera de producción y sin claves, una efímera."""
    raw = settings.fernet_keys.get_secret_value() if settings.fernet_keys else ""
    if parse_keys(raw):
        return _box(raw)
    if settings.environment == "production":  # pragma: no cover - create_app ya lo impide
        raise RuntimeError("UBW_FERNET_KEYS es obligatoria en producción")
    return _ephemeral_box()


@lru_cache(maxsize=1)
def _ephemeral_box() -> SecretBox:
    logger.warning("Sin UBW_FERNET_KEYS: se usa una clave efímera y los secretos no sobrevivirán al reinicio")
    return SecretBox([_EPHEMERAL_KEY])
