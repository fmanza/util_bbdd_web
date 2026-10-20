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
        app_secret_key: Clave de firma del token CSRF (ADR-003); obligatoria en producción.
        fernet_keys: Claves Fernet separadas por comas, la primera cifra (Fase 2, ADR-004).
        session_idle_minutes: Caducidad de la sesión por inactividad.
        session_absolute_hours: Caducidad absoluta de la sesión desde el inicio de sesión.
        login_max_attempts: Intentos fallidos seguidos que bloquean la cuenta.
        login_lockout_minutes: Duración del bloqueo temporal.
        password_min_length: Longitud mínima de contraseña (la máxima es fija, 128).
        files_dir: Única carpeta del servidor a la que pueden apuntar los parámetros de ruta de las conexiones
            (fichero SQLite, JAR de HSQLDB, certificados TLS…). Evita leer ficheros arbitrarios como ``config.db``.
        connection_test_timeout: Segundos máximos de una prueba de conexión o readiness (se mata el subproceso).
    """

    model_config = SettingsConfigDict(env_prefix="UBW_", secrets_dir=None, extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    data_dir: Path = Path("data")
    workspace_dir: Path = Path("workspace")
    static_dir: Path = Path("static")
    log_level: str = "INFO"
    app_secret_key: SecretStr | None = Field(default=None)
    fernet_keys: SecretStr | None = Field(default=None)
    session_idle_minutes: int = Field(default=60, ge=5, le=24 * 60)
    session_absolute_hours: int = Field(default=12, ge=1, le=24 * 30)
    login_max_attempts: int = Field(default=5, ge=1, le=100)
    login_lockout_minutes: int = Field(default=15, ge=1, le=24 * 60)
    password_min_length: int = Field(default=12, ge=8, le=128)
    files_dir: Path = Path("data/files")
    connection_test_timeout: float = Field(default=15.0, gt=0, le=120)

    @property
    def cookie_secure(self) -> bool:
        """``Secure`` en las cookies salvo en ``development`` (HTTP local sin TLS, ADR-003)."""
        return self.environment != "development"

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
