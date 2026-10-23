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
        worker_concurrency: Jobs simultáneos del worker (un subproceso cada uno, ADR-002).
        worker_poll_seconds: Intervalo de sondeo de la cola y del latido del worker.
        job_timeout_seconds: Duración máxima de un job; al superarla se mata su subproceso.
        max_queued_per_user: Ejecuciones en cola o en curso por usuario (429 al superarlo).
        user_quota_mb: Espacio de workspace por usuario (MB) de sus ejecuciones; ``0`` sin límite.
        run_retention_days: Se purgan las ejecuciones terminadas más antiguas; ``0`` desactiva.
        run_retention_per_project: Se conservan las N ejecuciones más recientes de cada proyecto; ``0`` desactiva.
        metadata_timeout_seconds: Tiempo máximo de lectura de schemas, snapshot o DDL (se mata el subproceso).
        query_timeout_seconds: Tiempo máximo de una query nombrada o de SQL libre.
        query_max_rows: Filas máximas que devuelve una query (el usuario puede pedir menos).
        upload_max_mb: Tamaño máximo de un fichero subido para la carga bulk (MB).
        upload_max_uncompressed_mb: Tamaño descomprimido máximo de un ``.xlsx`` (MB; frena las *zip bombs*).
        upload_retention_days: Días que se conservan los ficheros subidos; ``0`` sin purga.
        bulk_max_rows: Filas máximas de un fichero de carga bulk.
        rate_limit_enabled: Activa el rate limiting en memoria (Fase 10).
        rate_limit_api_per_minute: Peticiones por minuto a ``/api`` con sesión (por sesión).
        rate_limit_anonymous_per_minute: Peticiones por minuto a ``/api`` sin sesión (por IP).
        rate_limit_login_per_minute: Intentos de inicio de sesión por minuto y por IP.
        rate_limit_login_failures: Inicios de sesión fallidos por IP en 15 minutos antes de responder 429.
        rate_limit_uploads_per_hour: Subidas de ficheros por hora y por sesión.
        metrics_token: Token *bearer* de ``/metrics``; sin él, ``/metrics`` responde 404.
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
    worker_concurrency: int = Field(default=2, ge=1, le=32)
    worker_poll_seconds: float = Field(default=1.0, gt=0, le=60)
    job_timeout_seconds: int = Field(default=3600, ge=1, le=7 * 24 * 3600)
    max_queued_per_user: int = Field(default=5, ge=1, le=1000)
    user_quota_mb: int = Field(default=1024, ge=0)
    run_retention_days: int = Field(default=30, ge=0)
    run_retention_per_project: int = Field(default=100, ge=0)
    metadata_timeout_seconds: float = Field(default=120.0, gt=0, le=1800)
    query_timeout_seconds: float = Field(default=30.0, gt=0, le=600)
    query_max_rows: int = Field(default=1000, ge=1, le=10_000)
    upload_max_mb: int = Field(default=50, ge=1, le=2048)
    upload_max_uncompressed_mb: int = Field(default=300, ge=1, le=8192)
    upload_retention_days: int = Field(default=7, ge=0)
    bulk_max_rows: int = Field(default=1_000_000, ge=1, le=50_000_000)
    rate_limit_enabled: bool = True
    rate_limit_api_per_minute: int = Field(default=600, ge=1)
    rate_limit_anonymous_per_minute: int = Field(default=300, ge=1)
    rate_limit_login_per_minute: int = Field(default=30, ge=1)
    rate_limit_login_failures: int = Field(default=10, ge=1)
    rate_limit_uploads_per_hour: int = Field(default=60, ge=1)
    metrics_token: SecretStr | None = Field(default=None)

    @property
    def cookie_secure(self) -> bool:
        """``Secure`` en las cookies salvo en ``development`` (HTTP local sin TLS, ADR-003)."""
        return self.environment != "development"

    @property
    def cookie_prefix(self) -> str:
        """``__Host-`` con ``Secure`` (ASVS 3.4.4: sin ``Domain``, ``Path=/``; no la fija un subdominio)."""
        return "__Host-" if self.cookie_secure else ""

    @property
    def database_url(self) -> str:
        """URL SQLAlchemy de ``config.db``."""
        return f"sqlite:///{(self.data_dir / 'config.db').as_posix()}"


@lru_cache
def get_settings() -> Settings:
    """Ajustes del proceso, leídos una vez.

    Con ``/run/secrets`` presente (Docker secrets) lee de ahí ``app_secret_key``, ``fernet_keys`` y
    ``metrics_token``.
    """
    secrets_dir = Path("/run/secrets")
    if secrets_dir.is_dir():
        return Settings(_secrets_dir=secrets_dir)
    return Settings()
