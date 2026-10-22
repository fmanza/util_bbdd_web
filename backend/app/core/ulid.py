"""Identificadores ULID (26 caracteres Crockford base32, ordenables por tiempo) para las ejecuciones (ADR-005).

Implementación propia de unas líneas para no añadir dependencias: 48 bits de milisegundos + 80 bits aleatorios.
"""

from __future__ import annotations

import re
import secrets
import time

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ULID_PATTERN = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def new_ulid(timestamp_ms: int | None = None) -> str:
    """ULID nuevo; ``timestamp_ms`` permite fijar el instante (tests)."""
    ms = int(time.time() * 1000) if timestamp_ms is None else timestamp_ms
    value = (ms << 80) | secrets.randbits(80)
    chars = []
    for _ in range(26):
        value, index = divmod(value, 32)
        chars.append(_ALPHABET[index])
    return "".join(reversed(chars))


def is_ulid(value: str) -> bool:
    return bool(ULID_PATTERN.fullmatch(value))
