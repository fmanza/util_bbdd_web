"""Genera los secretos locales de Docker Compose en ``secrets/`` (git-ignored) si no existen.

- ``app_secret_key.txt``: clave aleatoria para firmar sesiones y tokens CSRF (Fase 1).
- ``fernet_keys.txt``: clave Fernet (base64 URL-safe de 32 bytes) para cifrar secretos de conexión (Fase 2,
  ADR-004). Para rotar, se antepone una clave nueva separada por coma; la primera cifra y todas descifran.
- ``metrics_token.txt``: token *bearer* de ``/metrics`` (Fase 10); solo se usa si se activa el secret
  ``ubw_metrics_token`` en ``docker-compose.yml``.

Uso::

    python scripts/generate_secrets.py
"""

from __future__ import annotations

import base64
import secrets
from pathlib import Path

SECRETS_DIR = Path(__file__).resolve().parents[1] / "secrets"


def _write_once(name: str, value: str) -> None:
    path = SECRETS_DIR / name
    if path.exists():
        print(f"{path.name}: ya existe, no se toca")
        return
    path.write_text(value, encoding="ascii", newline="")
    print(f"{path.name}: creado")


def main() -> None:
    SECRETS_DIR.mkdir(exist_ok=True)
    _write_once("app_secret_key.txt", secrets.token_urlsafe(48))
    _write_once("fernet_keys.txt", base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii"))
    _write_once("metrics_token.txt", secrets.token_urlsafe(32))


if __name__ == "__main__":
    main()
