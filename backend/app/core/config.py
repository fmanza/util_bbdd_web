"""Configuración de la aplicación leída de variables de entorno (prefijo ``UBW_``) y Docker secrets."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ajustes del proceso.

    Los secretos (clave de sesión y claves Fernet) se leen de ``/run/secrets`` cuando la aplicación corre con Docker
    secrets; nunca tienen valor por defecto en producción.

    Attributes:
        environment: ``development``, ``test`` o ``production``.
        data_dir: Carpeta de ``config.db`` (volumen ``data``).
        workspace_dir: Raíz de las salidas por ejecución (volumen ``workspace``).
        static_dir: Build del frontend servido por la API; si no existe, solo se sirve ``/api``.
        app_secret_key: Clave de firma de sesiones y CSRF (Fase 1).
        fernet_keys: Claves Fernet separadas por comas, la primera cifra (Fase 2, ADR-004).
    """

    model_config = SettingsConfigDict(env_prefix="UBW_", secrets_dir=None, extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    data_dir: Path = Path("data")
    workspace_dir: Path = Path("workspace")
    static_dir: Path = Path("static")
    log_level: str = "INFO"
    app_secret_key: SecretStr | None = Field(default=None)
    fernet_keys: SecretStr | None = Field(default=None)

    @property
    def database_url(self) -> str:
        """URL SQLAlchemy de ``config.db``."""
        return f"sqlite:///{(self.data_dir / 'config.db').as_posix()}"


@lru_cache
def get_settings() -> Settings:
    """Ajustes del proceso, leídos una vez.

    Con ``/run/secrets`` presente (Docker secrets) lee de ahí ``app_secret_key`` y ``fernet_keys``.
    """
    secrets_dir = Path("/run/secrets")
    if secrets_dir.is_dir():
        return Settings(_secrets_dir=secrets_dir)
    return Settings()
