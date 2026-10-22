"""Casos de uso de conexiones: CRUD con visibilidad, prueba de conexión y readiness.

Autorización (en el servicio, no solo en el router):

- Visibles: las propias y las compartidas. Una privada ajena da 404.
- Editables: las propias; las compartidas, además, cualquier admin. Visible pero no editable da 403.
- Solo un admin crea o convierte conexiones en compartidas.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Final, Literal

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Connection, MetadataCache, User, Visibility, utcnow
from app.domain.connections import allowlist
from app.domain.connections.crypto import SecretDecryptError, secret_box
from app.domain.connections.errors import (
    ConnectionForbiddenError,
    ConnectionNameTakenError,
    ConnectionNotFoundError,
    ConnectionParamsError,
    TooManyTestsError,
)
from app.domain.connections.params import resolve_paths, validate_params, with_timeouts
from app.domain.engines import get_engine
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.integrations.util_bbdd import probe
from app.integrations.util_bbdd.catalog import EngineDetail, InvalidParamsError, build_params

logger = logging.getLogger(__name__)

#: Pruebas y readiness simultáneos (cada uno es un subproceso).
MAX_CONCURRENT_PROBES: Final = 4
_PROBES = threading.BoundedSemaphore(MAX_CONCURRENT_PROBES)

ErrorCode = Literal["driver_missing", "invalid_config", "connection_failed", "timeout", "not_allowed", "unknown"]

ERROR_MESSAGES: Final[dict[str, str]] = {
    "driver_missing": "El driver del motor no está instalado en el servidor.",
    "invalid_config": "Los parámetros de conexión no son válidos para el motor.",
    "connection_failed": "No se pudo conectar: servidor inaccesible, credenciales incorrectas o BD inexistente.",
    "timeout": "La conexión no respondió a tiempo.",
    "not_allowed": "El destino no está en la lista de destinos permitidos. Pide a un administrador que lo añada.",
    "secret_unreadable": "No se puede descifrar la contraseña guardada: vuelve a introducirla.",
    "unknown": "Error inesperado al conectar.",
}


@dataclass(frozen=True)
class ConnectionData:
    """Alta o edición de una conexión; en edición, ``None`` significa «sin cambio»."""

    name: str | None = None
    db_type: str | None = None
    description: str | None = None
    params: dict[str, Any] | None = None
    password: str | None = None
    read_only: bool | None = None
    visibility: Visibility | None = None


@dataclass(frozen=True)
class CheckOutcome:
    """Resultado saneado de una prueba de conexión."""

    ok: bool
    duration_ms: int
    server_version: str | None
    error_code: str | None
    tested_at: datetime


@dataclass(frozen=True)
class ReadinessOutcome:
    """Resultado saneado de readiness."""

    report: probe.ReadinessResult | None
    error_code: str | None


# --- consultas ---------------------------------------------------------------------------------------------------


def _visible(user: User) -> Any:
    return or_(Connection.owner_id == user.id, Connection.visibility == "shared")


def can_edit(user: User, connection: Connection) -> bool:
    return connection.owner_id == user.id or (connection.visibility == "shared" and user.role == "admin")


def list_connections(
    db: Session, user: User, *, db_type: str | None, q: str | None, limit: int, offset: int
) -> tuple[list[Connection], int]:
    """Conexiones visibles para ``user`` ordenadas por nombre."""
    query = select(Connection).where(_visible(user))
    if db_type:
        query = query.where(Connection.db_type == db_type)
    if q:
        pattern = f"%{q.strip().lower()}%"
        query = query.where(
            or_(func.lower(Connection.name).like(pattern), func.lower(Connection.description).like(pattern))
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(func.lower(Connection.name), Connection.id).limit(limit).offset(offset)).all()
    return list(rows), total


def get_visible(db: Session, user: User, connection_id: int) -> Connection:
    """Conexión visible para ``user``.

    Raises:
        ConnectionNotFoundError: No existe o es privada de otro usuario.
    """
    connection = db.scalar(select(Connection).where(Connection.id == connection_id, _visible(user)))
    if connection is None:
        raise ConnectionNotFoundError()
    return connection


def get_editable(db: Session, user: User, connection_id: int) -> Connection:
    """Conexión que ``user`` puede modificar.

    Raises:
        ConnectionNotFoundError: No es visible.
        ConnectionForbiddenError: Visible pero ajena.
    """
    connection = get_visible(db, user, connection_id)
    if not can_edit(user, connection):
        raise ConnectionForbiddenError("Es una conexión compartida: solo un administrador puede modificarla.")
    return connection


# --- escritura ---------------------------------------------------------------------------------------------------


def _check_visibility(user: User, visibility: Visibility | None) -> None:
    if visibility == "shared" and user.role != "admin":
        raise ConnectionForbiddenError("Solo un administrador puede crear conexiones compartidas.")


def _check_name(db: Session, owner_id: int, name: str, exclude_id: int | None = None) -> str:
    name = name.strip()
    if not name:
        raise ConnectionParamsError("El nombre no puede estar vacío.", field="name")
    query = select(Connection.id).where(Connection.owner_id == owner_id, func.lower(Connection.name) == name.lower())
    if exclude_id is not None:
        query = query.where(Connection.id != exclude_id)
    if db.scalar(query) is not None:
        raise ConnectionNameTakenError()
    return name


def _check_required(engine: EngineDetail, params: dict[str, Any], password: str | None, settings: Settings) -> None:
    """Requeridos y combinaciones con ``build_conn_params`` de util_bbdd (sin conectar)."""
    secrets = {"password": password} if password else {}
    try:
        build_params(engine.db_type, {**resolve_paths(engine, params, settings), **secrets})
    except InvalidParamsError as exc:
        raise ConnectionParamsError(str(exc)) from None


def _stored_password(connection: Connection, settings: Settings) -> str | None:
    if not connection.secret_enc:
        return None
    password = secret_box(settings).decrypt(connection.secret_enc).get("password")
    return str(password) if password is not None else None


def _encrypt_password(password: str | None, settings: Settings) -> str | None:
    return secret_box(settings).encrypt({"password": password}) if password else None


def create_connection(
    db: Session, user: User, data: ConnectionData, *, settings: Settings, ctx: RequestContext
) -> Connection:
    """Crea una conexión del usuario.

    Raises:
        EngineNotFoundError, ConnectionParamsError, ConnectionNameTakenError, ConnectionForbiddenError.
    """
    assert data.name is not None and data.db_type is not None  # noqa: S101 - garantizado por el esquema HTTP
    engine = get_engine(data.db_type)
    _check_visibility(user, data.visibility)
    name = _check_name(db, user.id, data.name)
    params = validate_params(engine, data.params or {}, settings)
    _check_required(engine, params, data.password, settings)
    connection = Connection(
        owner_id=user.id,
        name=name,
        db_type=engine.db_type,
        description=(data.description or "").strip(),
        params=params,
        secret_enc=_encrypt_password(data.password, settings),
        visibility=data.visibility or "private",
        read_only=True if data.read_only is None else data.read_only,
    )
    db.add(connection)
    db.flush()
    audit.record(
        db,
        action=AuditAction.CONNECTION_CREATE,
        ctx=ctx,
        actor_id=user.id,
        target_type="connection",
        target_id=connection.id,
        details={"name": name, "db_type": engine.db_type, "visibility": connection.visibility},
    )
    db.commit()
    return connection


def update_connection(
    db: Session, user: User, connection: Connection, data: ConnectionData, *, settings: Settings, ctx: RequestContext
) -> Connection:
    """Edita una conexión editable por ``user``. ``password`` sustituye a la guardada; si se omite, se conserva."""
    engine = get_engine(connection.db_type)
    _check_visibility(user, data.visibility)
    changed: list[str] = []
    if data.name is not None and data.name.strip() != connection.name:
        connection.name = _check_name(db, connection.owner_id, data.name, exclude_id=connection.id)
        changed.append("name")
    if data.description is not None and data.description.strip() != connection.description:
        connection.description = data.description.strip()
        changed.append("description")
    if data.params is not None or data.password is not None:
        params = validate_params(engine, data.params, settings) if data.params is not None else connection.params
        try:
            password = data.password if data.password is not None else _stored_password(connection, settings)
        except SecretDecryptError:
            password = None
        _check_required(engine, params, password, settings)
        if params != connection.params:
            connection.params = params
            changed.append("params")
        if data.password is not None:
            connection.secret_enc = _encrypt_password(data.password, settings)
            changed.append("password")
        connection.last_test_at = connection.last_test_ok = connection.last_test_error = None
        db.execute(delete(MetadataCache).where(MetadataCache.connection_id == connection.id))
    if data.read_only is not None and data.read_only != connection.read_only:
        connection.read_only = data.read_only
        changed.append("read_only")
    if data.visibility is not None and data.visibility != connection.visibility:
        connection.visibility = data.visibility
        changed.append("visibility")
    if changed:
        audit.record(
            db,
            action=AuditAction.CONNECTION_UPDATE,
            ctx=ctx,
            actor_id=user.id,
            target_type="connection",
            target_id=connection.id,
            details={"fields": changed},
        )
    db.commit()
    return connection


def delete_connection(db: Session, user: User, connection: Connection, *, ctx: RequestContext) -> None:
    audit.record(
        db,
        action=AuditAction.CONNECTION_DELETE,
        ctx=ctx,
        actor_id=user.id,
        target_type="connection",
        target_id=connection.id,
        details={"name": connection.name, "db_type": connection.db_type},
    )
    db.delete(connection)
    db.commit()


def rotate_secrets(db: Session, settings: Settings) -> int:
    """Vuelve a cifrar todos los secretos con la clave Fernet principal (rotación, ADR-004).

    Raises:
        SecretDecryptError: Algún secreto no se descifra con las claves configuradas (no se guarda nada).
    """
    box = secret_box(settings)
    rows = db.scalars(select(Connection).where(Connection.secret_enc.is_not(None))).all()
    for connection in rows:
        assert connection.secret_enc is not None  # noqa: S101 - filtrado en la consulta
        connection.secret_enc = box.rotate(connection.secret_enc)
    db.commit()
    return len(rows)


# --- prueba y readiness ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PreparedConnection:
    conn_params: dict[str, Any] | None
    error_code: str | None


def _fixed(addresses: list[allowlist.IPAddress]) -> allowlist.Resolver:
    """*Resolver* que devuelve las IP ya resueltas (una sola resolución DNS por comprobación)."""

    def resolve(_host: str) -> list[allowlist.IPAddress]:
        return addresses

    return resolve


def prepare_connection(db: Session, connection: Connection, settings: Settings) -> PreparedConnection:
    """``conn_params`` listos para conectar, o el código de error que impide intentarlo."""
    engine = get_engine(connection.db_type)
    try:
        password = _stored_password(connection, settings)
    except SecretDecryptError:
        return PreparedConnection(None, "secret_unreadable")
    secrets = {"password": password} if password else {}
    try:
        conn_params = build_params(engine.db_type, {**resolve_paths(engine, connection.params, settings), **secrets})
    except InvalidParamsError:
        return PreparedConnection(None, "invalid_config")
    policy = allowlist.current_policy(db)
    for host in allowlist.target_hosts(engine.db_type, conn_params):
        try:
            addresses = allowlist.resolve(host)
        except OSError:
            return PreparedConnection(
                None, "connection_failed"
            )  # el nombre no resuelve: no es un problema de la allowlist
        if not allowlist.is_allowed(host, policy, _fixed(addresses)):
            return PreparedConnection(None, "not_allowed")
    return PreparedConnection(with_timeouts(engine.db_type, conn_params), None)


@contextmanager
def probe_slot() -> Iterator[None]:
    """Reserva uno de los ``MAX_CONCURRENT_PROBES`` subprocesos interactivos (pruebas, metadatos y SQL).

    Raises:
        TooManyTestsError: Están todos ocupados (429).
    """
    if not _PROBES.acquire(blocking=False):
        raise TooManyTestsError()
    try:
        yield
    finally:
        _PROBES.release()


def run_test(
    db: Session, user: User, connection: Connection, *, settings: Settings, ctx: RequestContext
) -> CheckOutcome:
    """Prueba la conexión en un subproceso y guarda el resultado en ``last_test_*``.

    Raises:
        TooManyTestsError: Ya hay ``MAX_CONCURRENT_PROBES`` en curso.
    """
    prepared = prepare_connection(db, connection, settings)
    db.commit()  # cierra la transacción de lectura antes de una espera larga (SQLite, un escritor)
    outcome: CheckOutcome
    if prepared.conn_params is None:
        outcome = CheckOutcome(False, 0, None, prepared.error_code, utcnow())
    else:
        with probe_slot():
            result = probe.check_connection(
                connection.db_type, prepared.conn_params, timeout=settings.connection_test_timeout
            )
        if result.error is not None:
            logger.info(
                "Prueba de conexión fallida",
                extra={"connection_id": connection.id, "code": result.error.code, "exc_type": result.error.exc_type},
            )
        outcome = CheckOutcome(
            result.ok,
            result.duration_ms,
            result.server_version,
            result.error.code if result.error else None,
            utcnow(),
        )
    connection.last_test_at = outcome.tested_at
    connection.last_test_ok = outcome.ok
    connection.last_test_error = outcome.error_code
    audit.record(
        db,
        action=AuditAction.CONNECTION_TEST,
        ctx=ctx,
        actor_id=user.id,
        outcome="success" if outcome.ok else "failure",
        target_type="connection",
        target_id=connection.id,
        details={"error": outcome.error_code} if outcome.error_code else None,
    )
    db.commit()
    return outcome


def readiness(
    db: Session, user: User, connection: Connection, *, settings: Settings, ctx: RequestContext
) -> ReadinessOutcome:
    """Readiness del motor (``get_engine_readiness``) en un subproceso; los valores de parámetros secretos se ocultan.

    Raises:
        TooManyTestsError: Ya hay ``MAX_CONCURRENT_PROBES`` en curso.
    """
    prepared = prepare_connection(db, connection, settings)
    db.commit()
    if prepared.conn_params is None:
        outcome = ReadinessOutcome(None, prepared.error_code)
    else:
        with probe_slot():
            report = probe.engine_readiness(
                connection.db_type, prepared.conn_params, timeout=settings.connection_test_timeout
            )
        secret_params = {spec.name for spec in get_engine(connection.db_type).params if spec.kind == "secret"}
        report = replace(
            report,
            findings=tuple(replace(f, current="********") if f.param in secret_params else f for f in report.findings),
        )
        outcome = ReadinessOutcome(report, report.error.code if report.error else None)
    audit.record(
        db,
        action=AuditAction.CONNECTION_READINESS,
        ctx=ctx,
        actor_id=user.id,
        outcome="failure" if outcome.error_code else "success",
        target_type="connection",
        target_id=connection.id,
        details={"error": outcome.error_code} if outcome.error_code else None,
    )
    db.commit()
    return outcome
