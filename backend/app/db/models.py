"""Modelos SQLAlchemy de ``config.db``.

Fase 1: identidad (``users``, ``sessions``, ``audit_log``).
Fase 2: conexiones (``connections``) y allowlist de destinos (``allowlist_entries``).
Fase 3: proyectos (``projects``, ``project_members``, ``project_connections``), ejecuciones (``runs``,
``artifacts``) y latido del worker (``workers``).
Fase 4: caché de metadatos (``metadata_cache``), queries nombradas (``named_queries``) y ``users.can_run_sql``.
Fase 7: ``users.can_apply_ddl`` (aplicar migraciones DDL en una BD destino, ADR-008).
Fase 8: ``users.can_write_data`` (volcar datos en una BD destino, ADR-009).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

Role = Literal["admin", "user"]
ROLES: tuple[Role, ...] = ("admin", "user")
Visibility = Literal["private", "shared"]
ProjectRole = Literal["owner", "editor", "viewer"]
PROJECT_ROLES: tuple[ProjectRole, ...] = ("owner", "editor", "viewer")
RunStatus = Literal["queued", "running", "succeeded", "failed", "cancelled", "purged"]
TERMINAL_STATUSES: frozenset[str] = frozenset({"succeeded", "failed", "cancelled"})


def utcnow() -> datetime:
    """Instante actual en UTC con zona."""
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Fecha en UTC: SQLite la guarda sin zona y se devuelve siempre con ``tzinfo=UTC``."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Se esperaba una fecha con zona horaria")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return None if value is None else value.replace(tzinfo=UTC)


class User(Base):
    """Usuario de la aplicación. No se borra: se desactiva (la auditoría lo referencia)."""

    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('admin', 'user')", name="role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(default=True)
    can_run_sql: Mapped[bool] = mapped_column(default=False)
    can_apply_ddl: Mapped[bool] = mapped_column(default=False)
    can_write_data: Mapped[bool] = mapped_column(default=False)
    failed_attempts: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    password_changed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    sessions: Mapped[list[UserSession]] = relationship(back_populates="user", passive_deletes=True)


class UserSession(Base):
    """Sesión de servidor. Solo se guarda el SHA-256 del token; el token viaja en la cookie ``ubw_session``."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    ip: Mapped[str | None] = mapped_column(String(64), default=None)
    user_agent: Mapped[str | None] = mapped_column(String(255), default=None)

    user: Mapped[User] = relationship(back_populates="sessions")


class AuditEntry(Base):
    """Evento de auditoría. ``details`` nunca contiene secretos."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_ts", "ts"), Index("ix_audit_log_action", "action"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    action: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(16), default="success")
    target_type: Mapped[str | None] = mapped_column(String(32), default=None)
    target_id: Mapped[str | None] = mapped_column(String(64), default=None)
    ip: Mapped[str | None] = mapped_column(String(64), default=None)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)

    actor: Mapped[User | None] = relationship(lazy="joined")

    @property
    def actor_username(self) -> str | None:
        """Usuario que hizo la acción, si lo hay."""
        return self.actor.username if self.actor else None


class Connection(Base):
    """Conexión a una BD destino.

    ``params`` no contiene secretos; la contraseña va cifrada con Fernet en ``secret_enc`` (ADR-004). Las privadas
    solo las ve su propietario; las compartidas (``shared``, creadas por un admin) las usan todos sin ver el secreto.
    """

    __tablename__ = "connections"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_connections_owner_id_name"),
        CheckConstraint("visibility IN ('private', 'shared')", name="visibility"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    db_type: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(String(500), default="")
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    secret_enc: Mapped[str | None] = mapped_column(Text, default=None)
    visibility: Mapped[str] = mapped_column(String(16), default="private")
    read_only: Mapped[bool] = mapped_column(default=True)
    last_test_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    last_test_ok: Mapped[bool | None] = mapped_column(default=None)
    last_test_error: Mapped[str | None] = mapped_column(String(32), default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    owner: Mapped[User] = relationship(lazy="joined")


class AllowlistEntry(Base):
    """Destino permitido para las conexiones salientes (anti-SSRF): red CIDR o nombre de host (``*.dominio``)."""

    __tablename__ = "allowlist_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pattern: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str] = mapped_column(String(255), default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class Project(Base):
    """Proyecto: agrupa miembros, conexiones con alias y ejecuciones.

    ``owner_id`` es el creador y fija la ruta del workspace (ADR-005); la propiedad efectiva la dan los miembros con
    rol ``owner``.
    """

    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_projects_owner_id_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    members: Mapped[list[ProjectMember]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )


class ProjectMember(Base):
    """Pertenencia de un usuario a un proyecto con su rol."""

    __tablename__ = "project_members"
    __table_args__ = (CheckConstraint("role IN ('owner', 'editor', 'viewer')", name="role"),)

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    role: Mapped[str] = mapped_column(String(16))
    added_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="members")
    user: Mapped[User] = relationship(lazy="joined")


class ProjectConnection(Base):
    """Conexión asociada a un proyecto con un alias (``origen``, ``destino``…) que usan las ejecuciones."""

    __tablename__ = "project_connections"
    __table_args__ = (UniqueConstraint("project_id", "alias", name="uq_project_connections_project_id_alias"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    connection_id: Mapped[int] = mapped_column(ForeignKey("connections.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(String(32))
    added_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    connection: Mapped[Connection] = relationship(lazy="joined")


class Run(Base):
    """Ejecución de una operación de util_bbdd (o ``noop``) en un proyecto; la tabla es la cola del worker.

    ``params`` no contiene secretos; las conexiones se referencian por alias del proyecto. ``manifest`` copia
    ``run.json`` y se conserva al purgar.
    """

    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled', 'purged')", name="status"),
        Index("ix_runs_project_id_created_at", "project_id", "created_at"),
        Index("ix_runs_status_created_at", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    operation: Mapped[str] = mapped_column(String(32))
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    phase: Mapped[str | None] = mapped_column(String(16), default=None)
    progress_message: Mapped[str | None] = mapped_column(String(255), default=None)
    progress_pct: Mapped[int | None] = mapped_column(default=None)
    error_code: Mapped[str | None] = mapped_column(String(32), default=None)
    error_message: Mapped[str | None] = mapped_column(String(500), default=None)
    cancel_requested: Mapped[bool] = mapped_column(default=False)
    worker_id: Mapped[str | None] = mapped_column(String(64), default=None)
    heartbeat_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    workspace_path: Mapped[str | None] = mapped_column(String(255), default=None)
    size_bytes: Mapped[int] = mapped_column(default=0)
    manifest: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    relaunched_from: Mapped[str | None] = mapped_column(String(26), default=None)

    project: Mapped[Project] = relationship(lazy="joined")
    user: Mapped[User | None] = relationship(lazy="joined")
    artifacts: Mapped[list[Artifact]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True, order_by="Artifact.path"
    )


class Artifact(Base):
    """Fichero generado por una ejecución (ruta relativa a la carpeta del run)."""

    __tablename__ = "artifacts"
    __table_args__ = (UniqueConstraint("run_id", "path", name="uq_artifacts_run_id_path"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(16))
    mime: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(default=0)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    run: Mapped[Run] = relationship(back_populates="artifacts")


class Worker(Base):
    """Latido de un proceso worker (``/api/health`` informa si hay uno vivo)."""

    __tablename__ = "workers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    pid: Mapped[int] = mapped_column()
    hostname: Mapped[str] = mapped_column(String(255))
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    heartbeat_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class MetadataCache(Base):
    """Snapshot de metadatos de un schema de una conexión (JSON comprimido con zlib); se invalida a mano o al editar
    la conexión."""

    __tablename__ = "metadata_cache"

    connection_id: Mapped[int] = mapped_column(ForeignKey("connections.id", ondelete="CASCADE"), primary_key=True)
    schema: Mapped[str] = mapped_column(String(128), primary_key=True)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    size_bytes: Mapped[int] = mapped_column(default=0)
    payload: Mapped[bytes] = mapped_column(LargeBinary)


class NamedQuery(Base):
    """Query nombrada de solo lectura para un motor (la gestionan los admins).

    ``sql_template`` usa ``{param}`` como util_bbdd (``str.format``); al ejecutar, cada parámetro debe tener forma de
    identificador o número y el SQL final pasa por el guardián de solo lectura.
    """

    __tablename__ = "named_queries"
    __table_args__ = (UniqueConstraint("db_type", "name", name="uq_named_queries_db_type_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    db_type: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(500), default="")
    sql_template: Mapped[str] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
