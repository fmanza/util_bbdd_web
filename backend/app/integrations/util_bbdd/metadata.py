"""Metadatos de util_bbdd para el explorador (Fase 4): schemas, snapshot serializado y DDL.

Las tareas (``*_task``) se ejecutan en el subproceso de :mod:`isolated`; las funciones públicas las lanzan con timeout.
El snapshot se devuelve como ``dict`` de tipos simples (a partir de los modelos neutros de ``util_bbdd.metadata``) para
cachearlo en ``config.db`` sin depender de util_bbdd fuera de esta capa.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Literal

from app.integrations.util_bbdd.isolated import TaskResult, run_isolated

ObjectKind = Literal["table", "view", "routine"]

#: Schemas de sistema por motor (se marcan para ocultarlos por defecto en la UI).
SYSTEM_SCHEMAS: dict[str, frozenset[str]] = {
    "postgresql": frozenset({"information_schema", "pg_catalog", "pg_toast"}),
    "sqlserver": frozenset(
        {"sys", "INFORMATION_SCHEMA", "guest", "db_owner", "db_accessadmin", "db_securityadmin", "db_ddladmin",
         "db_backupoperator", "db_datareader", "db_datawriter", "db_denydatareader", "db_denydatawriter"}
    ),
    "mysql": frozenset({"information_schema", "mysql", "performance_schema", "sys"}),
    "mariadb": frozenset({"information_schema", "mysql", "performance_schema", "sys"}),
    "oracle": frozenset(
        {"SYS", "SYSTEM", "XDB", "OUTLN", "DBSNMP", "APPQOSSYS", "AUDSYS", "CTXSYS", "DVSYS", "GSMADMIN_INTERNAL",
         "LBACSYS", "MDSYS", "OJVMSYS", "OLAPSYS", "ORDDATA", "ORDSYS", "WMSYS", "DVF", "GGSYS", "REMOTE_SCHEDULER_AGENT",
         "SYSBACKUP", "SYSDG", "SYSKM", "SYSRAC", "SYS$UMF", "ANONYMOUS", "DIP", "GSMCATUSER", "GSMUSER", "XS$NULL",
         "ORACLE_OCM", "MDDATA", "GSMROOTUSER", "DBSFWUSER", "PDBADMIN", "VECSYS", "OPS$ORACLE", "GSMSYS"}
    ),
    "hsqldb": frozenset({"INFORMATION_SCHEMA", "SYSTEM_LOBS"}),
}  # fmt: skip


def _plain(value: Any) -> Any:
    """Modelos de util_bbdd (dataclasses congeladas) a tipos simples."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, tuple | list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _manager(db_type: str, conn_params: dict[str, Any]) -> Any:
    from util_bbdd import SyncDatabaseManager

    return SyncDatabaseManager(db_type, conn_params, use_pool=False)


# --- tareas del subproceso ---------------------------------------------------------------------------------------


def schemas_task(db_type: str, conn_params: dict[str, Any]) -> dict[str, Any]:
    """Schemas visibles (``sqlalchemy.inspect(engine).get_schema_names()``, GAPS G17) y el de por defecto."""
    from sqlalchemy import inspect

    with _manager(db_type, conn_params) as manager:
        engine = manager.get_sqlalchemy_engine()
        inspector = inspect(engine)
        # SQLAlchemy normaliza a minúsculas los nombres sin comillas de Oracle (``BENCH`` → ``bench``); util_bbdd
        # necesita el nombre real del catálogo.
        dialect = engine.dialect

        def real(name: str) -> str:
            return str(dialect.denormalize_name(name) or name) if dialect.requires_name_normalize else str(name)

        names = sorted(real(n) for n in inspector.get_schema_names())
        default = real(inspector.default_schema_name) if inspector.default_schema_name else None
    system = SYSTEM_SCHEMAS.get(db_type, frozenset())
    return {
        "default": str(default) if default else (names[0] if names else None),
        "schemas": [{"name": n, "system": n in system or n.upper() in system} for n in names],
    }


def snapshot_task(db_type: str, conn_params: dict[str, Any], schema: str) -> dict[str, Any]:
    """``SyncDatabaseManager.get_schema_metadata(schema)`` serializado (todas las clases de objeto)."""
    from util_bbdd.metadata import KindNotLoadedError

    with _manager(db_type, conn_params) as manager:
        snapshot = manager.get_schema_metadata(schema)

    def safe(call: Any, default: Any) -> Any:
        try:
            return call()
        except KindNotLoadedError:
            return default

    tables = safe(snapshot.tables, ())
    names = [t.name for t in tables]
    routines = safe(snapshot.routines, ())
    database = safe(snapshot.database, None)
    return {
        "engine": snapshot.engine,
        "schema": snapshot.schema,
        "database": _plain(database),
        "tables": _plain(tables),
        "views": _plain(safe(snapshot.views, ())),
        "routines": [
            {**_plain(r), "parameters": _plain(safe(lambda r=r: snapshot.routine_parameters(r.key), ()))}
            for r in routines
        ],
        "columns": {n: _plain(safe(lambda n=n: snapshot.columns(n), ())) for n in names},
        "primary_keys": {n: _plain(safe(lambda n=n: snapshot.primary_key(n), None)) for n in names},
        "uniques": {n: _plain(safe(lambda n=n: snapshot.uniques(n), ())) for n in names},
        "checks": {n: _plain(safe(lambda n=n: snapshot.checks(n), ())) for n in names},
        "indexes": {n: _plain(safe(lambda n=n: snapshot.indexes(n), ())) for n in names},
        "identity": {n: _plain(safe(lambda n=n: snapshot.identity(n), ())) for n in names},
        "foreign_keys": _plain(safe(snapshot.all_foreign_keys, ())),
    }


def ddl_task(db_type: str, conn_params: dict[str, Any], schema: str, kind: ObjectKind, name: str) -> str:
    """DDL con ``util_bbdd.metadata.ddl``: tablas nativas (``native_table_ddl_sql``) o reconstruidas (MySQL/MariaDB),
    vistas (``view_ddl``) y rutinas (``routine_ddl``)."""
    from sqlalchemy import text
    from util_bbdd.metadata import Kind
    from util_bbdd.metadata.ddl import mysql_table_ddl, native_table_ddl, native_table_ddl_sql, routine_ddl, view_ddl

    with _manager(db_type, conn_params) as manager:
        if kind == "view":
            snapshot = manager.get_schema_metadata(schema, kinds={Kind.VIEWS})
            return view_ddl(next((v for v in snapshot.views() if v.name == name), None), name)
        if kind == "routine":
            snapshot = manager.get_schema_metadata(schema, kinds={Kind.ROUTINES})
            return routine_ddl(next((r for r in snapshot.routines() if r.name == name), None))
        if db_type in ("mysql", "mariadb"):
            snapshot = manager.get_schema_metadata(schema, kinds={Kind.COLUMNS, Kind.PRIMARY_KEYS}, tables=[name])
            return mysql_table_ddl(name, snapshot.columns(name), snapshot.primary_key(name))
        sql = native_table_ddl_sql(db_type)
        if sql is None:
            return ""
        with manager.get_sqlalchemy_engine().connect() as connection:
            rows = connection.execute(text(sql), {"schema": schema, "table_name": name}).fetchall()
            connection.rollback()
        return native_table_ddl([tuple(r) for r in rows])


# --- API para el dominio -----------------------------------------------------------------------------------------


def list_schemas(db_type: str, conn_params: dict[str, Any], *, timeout: float) -> TaskResult:
    return run_isolated(f"{__name__}:schemas_task", {"db_type": db_type, "conn_params": conn_params}, timeout=timeout)


def read_snapshot(db_type: str, conn_params: dict[str, Any], schema: str, *, timeout: float) -> TaskResult:
    return run_isolated(
        f"{__name__}:snapshot_task", {"db_type": db_type, "conn_params": conn_params, "schema": schema}, timeout=timeout
    )


def read_ddl(
    db_type: str, conn_params: dict[str, Any], schema: str, kind: ObjectKind, name: str, *, timeout: float
) -> TaskResult:
    return run_isolated(
        f"{__name__}:ddl_task",
        {"db_type": db_type, "conn_params": conn_params, "schema": schema, "kind": kind, "name": name},
        timeout=timeout,
    )
