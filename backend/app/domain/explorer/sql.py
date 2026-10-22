"""Queries nombradas (CRUD de admins, ejecución por cualquiera que vea la conexión) y SQL libre restringido.

SQL libre: permiso ``users.can_run_sql`` + rol ``editor`` en el proyecto + conexión del proyecto con
``read_only = true`` + guardián de solo lectura + transacción de solo lectura en el motor (ver
``app/integrations/util_bbdd/sql.py``). Se audita con el texto (truncado) de la consulta.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Connection, NamedQuery, User
from app.domain.connections.service import prepare_connection, probe_slot
from app.domain.engines import get_engine
from app.domain.explorer.errors import (
    ConnectionNotReadOnlyError,
    DatabaseAccessError,
    DatabaseTimeoutError,
    NamedQueryInvalidError,
    NamedQueryNameTakenError,
    NamedQueryNotFoundError,
    SqlNotAllowedError,
    SqlRejectedError,
)
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.projects.service import get_membership, get_project_connection
from app.integrations.util_bbdd import sql as sql_engine
from app.integrations.util_bbdd.isolated import TaskResult

MAX_SQL_CHARS: Final = 100_000
AUDIT_SQL_CHARS: Final = 2000


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[list[Any]]
    truncated: bool
    row_count: int
    duration_ms: int


def _limit(requested: int | None, settings: Settings) -> int:
    return max(1, min(requested or settings.query_max_rows, settings.query_max_rows))


def _result(result: TaskResult) -> QueryResult:
    if result.error is not None:
        code = result.error.code
        if code == "timeout":
            raise DatabaseTimeoutError("timeout")
        if code in ("query_error", "not_read_only", "invalid_config") and result.error.message:
            raise SqlRejectedError(code, result.error.message)
        raise DatabaseAccessError(code)
    value = result.value
    return QueryResult(value["columns"], value["rows"], value["truncated"], value["row_count"], value["duration_ms"])


def _conn_params(db: Session, connection: Connection, settings: Settings) -> dict[str, Any]:
    prepared = prepare_connection(db, connection, settings)
    db.commit()
    if prepared.conn_params is None:
        raise DatabaseAccessError(prepared.error_code or "unknown")
    return prepared.conn_params


# --- SQL libre ---------------------------------------------------------------------------------------------------


def run_free_sql(
    db: Session,
    user: User,
    *,
    project_id: int,
    alias: str,
    sql: str,
    limit: int | None,
    settings: Settings,
    ctx: RequestContext,
) -> QueryResult:
    """Ejecuta una consulta de lectura sobre una conexión del proyecto.

    Raises:
        ProjectNotFoundError, ProjectForbiddenError: No es miembro o no es editor.
        SqlNotAllowedError: Sin ``can_run_sql``.
        ProjectConnectionNotFoundError: Alias desconocido.
        ConnectionNotReadOnlyError: La conexión no es ``read_only``.
        SqlRejectedError: No es una única sentencia de lectura, o el motor la rechaza (mensaje recortado).
        DatabaseAccessError, DatabaseTimeoutError.
    """
    membership = get_membership(db, user, project_id, "editor")
    if not user.can_run_sql:
        raise SqlNotAllowedError("Pide a un administrador el permiso «Puede ejecutar SQL».")
    connection = get_project_connection(db, membership.project, alias).connection
    if not connection.read_only:
        raise ConnectionNotReadOnlyError("Marca la conexión como «Solo lectura» para usar SQL libre sobre ella.")
    if len(sql) > MAX_SQL_CHARS:
        raise SqlRejectedError("not_read_only", f"La consulta supera {MAX_SQL_CHARS} caracteres.")
    try:
        sql_engine.check_read_only(sql, connection.db_type)
    except sql_engine.ReadOnlyViolation as exc:
        _audit_sql(db, user, ctx, connection, sql, outcome="failure", details={"error": "not_read_only"})
        raise SqlRejectedError("not_read_only", str(exc)) from None
    params = _conn_params(db, connection, settings)
    with probe_slot():
        raw = sql_engine.run_free_sql(
            connection.db_type, params, sql, limit=_limit(limit, settings), timeout=settings.query_timeout_seconds
        )
    try:
        result = _result(raw)
    except Exception as exc:
        _audit_sql(
            db, user, ctx, connection, sql, outcome="failure", details={"error": getattr(exc, "code", "unknown")}
        )
        raise
    _audit_sql(
        db, user, ctx, connection, sql, outcome="success",
        details={"rows": result.row_count, "truncated": result.truncated, "duration_ms": result.duration_ms},
    )  # fmt: skip
    return result


def _audit_sql(
    db: Session,
    user: User,
    ctx: RequestContext,
    connection: Connection,
    sql: str,
    *,
    outcome: str,
    details: dict[str, Any],
) -> None:
    audit.record(
        db, action=AuditAction.SQL_EXECUTE, ctx=ctx, actor_id=user.id, outcome=outcome, target_type="connection",
        target_id=connection.id, details={"sql": sql[:AUDIT_SQL_CHARS], **details},
    )  # fmt: skip
    db.commit()


def free_sql_supported(db_type: str) -> bool:
    return db_type in sql_engine.DIALECTS


def read_only_transaction(db_type: str) -> bool:
    return db_type not in sql_engine.WITHOUT_READ_ONLY_TRANSACTION


# --- queries nombradas -------------------------------------------------------------------------------------------


def list_named_queries(db: Session, *, db_type: str | None = None) -> list[NamedQuery]:
    query = select(NamedQuery)
    if db_type:
        query = query.where(NamedQuery.db_type == db_type)
    return list(db.scalars(query.order_by(NamedQuery.db_type, func.lower(NamedQuery.name))))


def get_named_query(db: Session, query_id: int) -> NamedQuery:
    query = db.get(NamedQuery, query_id)
    if query is None:
        raise NamedQueryNotFoundError()
    return query


def query_params(query: NamedQuery) -> list[str]:
    try:
        return sql_engine.template_params(query.sql_template)
    except ValueError:
        return []


def _validate_template(db_type: str, sql_template: str) -> None:
    get_engine(db_type)
    try:
        sql_engine.check_template(sql_template, db_type)
    except (ValueError, sql_engine.ReadOnlyViolation) as exc:
        raise NamedQueryInvalidError(
            str(exc), errors=[{"loc": ["body", "sql_template"], "msg": str(exc), "type": "value_error"}]
        ) from None


def _check_name(db: Session, db_type: str, name: str, exclude_id: int | None = None) -> None:
    query = select(NamedQuery.id).where(NamedQuery.db_type == db_type, func.lower(NamedQuery.name) == name.lower())
    if exclude_id is not None:
        query = query.where(NamedQuery.id != exclude_id)
    if db.scalar(query) is not None:
        raise NamedQueryNameTakenError()


def create_named_query(
    db: Session, admin: User, *, db_type: str, name: str, description: str, sql_template: str, ctx: RequestContext
) -> NamedQuery:
    _validate_template(db_type, sql_template)
    _check_name(db, db_type, name)
    query = NamedQuery(
        db_type=db_type,
        name=name,
        description=description.strip(),
        sql_template=sql_template.strip(),
        created_by=admin.id,
    )
    db.add(query)
    db.flush()
    audit.record(
        db, action=AuditAction.QUERY_CREATE, ctx=ctx, actor_id=admin.id, target_type="query", target_id=query.id,
        details={"name": name, "db_type": db_type},
    )  # fmt: skip
    db.commit()
    return query


def update_named_query(
    db: Session,
    admin: User,
    query: NamedQuery,
    *,
    name: str | None,
    description: str | None,
    sql_template: str | None,
    ctx: RequestContext,
) -> NamedQuery:
    if sql_template is not None:
        _validate_template(query.db_type, sql_template)
        query.sql_template = sql_template.strip()
    if name is not None and name != query.name:
        _check_name(db, query.db_type, name, exclude_id=query.id)
        query.name = name
    if description is not None:
        query.description = description.strip()
    audit.record(
        db, action=AuditAction.QUERY_UPDATE, ctx=ctx, actor_id=admin.id, target_type="query", target_id=query.id
    )
    db.commit()
    return query


def delete_named_query(db: Session, admin: User, query: NamedQuery, *, ctx: RequestContext) -> None:
    audit.record(
        db, action=AuditAction.QUERY_DELETE, ctx=ctx, actor_id=admin.id, target_type="query", target_id=query.id,
        details={"name": query.name, "db_type": query.db_type},
    )  # fmt: skip
    db.delete(query)
    db.commit()


def run_named_query(
    db: Session,
    user: User,
    connection: Connection,
    query: NamedQuery,
    *,
    params: dict[str, Any],
    limit: int | None,
    settings: Settings,
    ctx: RequestContext,
) -> QueryResult:
    """Ejecuta una query nombrada del motor de la conexión.

    Raises:
        NamedQueryNotFoundError: La query es de otro motor.
        NamedQueryInvalidError: Faltan o sobran parámetros, o algún valor no es identificador ni número (GAPS G18).
    """
    if query.db_type != connection.db_type:
        raise NamedQueryNotFoundError("La query no es de este motor.")
    expected = query_params(query)
    missing = [p for p in expected if p not in params]
    extra = [p for p in params if p not in expected]
    errors = [{"loc": ["body", "params", p], "msg": "Obligatorio", "type": "missing"} for p in missing]
    errors += [{"loc": ["body", "params", p], "msg": "No es un parámetro de la query", "type": "extra"} for p in extra]
    values: dict[str, str] = {}
    for name in expected:
        if name in params:
            value = str(params[name]).strip()
            if not sql_engine.PARAM_VALUE.fullmatch(value):
                errors.append({
                    "loc": ["body", "params", name],
                    "msg": "Solo identificadores (letras, números, _ $ #) o números",
                    "type": "value_error",
                })  # fmt: skip
            values[name] = value
    if errors:
        raise NamedQueryInvalidError("Revisa los parámetros de la query.", errors=errors)
    conn_params = _conn_params(db, connection, settings)
    with probe_slot():
        raw = sql_engine.run_named_query(
            connection.db_type, conn_params, name=query.name, sql_template=query.sql_template, params=values,
            limit=_limit(limit, settings), timeout=settings.query_timeout_seconds,
        )  # fmt: skip
    outcome = "success" if raw.error is None else "failure"
    audit.record(
        db, action=AuditAction.QUERY_EXECUTE, ctx=ctx, actor_id=user.id, outcome=outcome, target_type="connection",
        target_id=connection.id, details={"query": query.name, "params": values,
                                          **({"error": raw.error.code} if raw.error else {})},
    )  # fmt: skip
    db.commit()
    return _result(raw)
