"""Explorador de metadatos: schemas, snapshot cacheado por conexión y schema, detalle de tabla y DDL.

Cualquier usuario que vea la conexión (propia o compartida) puede explorarla: es lectura del catálogo. El snapshot se
guarda comprimido en ``metadata_cache`` y se invalida a mano (*Refrescar*) o al editar la conexión.
"""

from __future__ import annotations

import json
import zlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Connection, MetadataCache, utcnow
from app.domain.connections.service import prepare_connection, probe_slot
from app.domain.explorer.errors import DatabaseAccessError, DatabaseTimeoutError, ObjectNotFoundError
from app.integrations.util_bbdd import metadata
from app.integrations.util_bbdd.isolated import TaskResult
from app.integrations.util_bbdd.metadata import ObjectKind


@dataclass(frozen=True)
class CachedSnapshot:
    data: dict[str, Any]
    fetched_at: datetime
    size_bytes: int


def _conn_params(db: Session, connection: Connection, settings: Settings) -> dict[str, Any]:
    prepared = prepare_connection(db, connection, settings)
    db.commit()  # cierra la transacción de lectura antes de una espera larga
    if prepared.conn_params is None:
        raise DatabaseAccessError(prepared.error_code or "unknown")
    return prepared.conn_params


def _value(result: TaskResult) -> Any:
    if result.error is not None:
        if result.error.code == "timeout":
            raise DatabaseTimeoutError("timeout")
        raise DatabaseAccessError(result.error.code)
    return result.value


def list_schemas(db: Session, connection: Connection, settings: Settings) -> dict[str, Any]:
    params = _conn_params(db, connection, settings)
    with probe_slot():
        return dict(
            _value(metadata.list_schemas(connection.db_type, params, timeout=settings.metadata_timeout_seconds))
        )


def _load(db: Session, connection_id: int, schema: str) -> CachedSnapshot | None:
    row = db.get(MetadataCache, (connection_id, schema))
    if row is None:
        return None
    return CachedSnapshot(json.loads(zlib.decompress(row.payload)), row.fetched_at, row.size_bytes)


def get_snapshot(
    db: Session, connection: Connection, schema: str, settings: Settings, *, refresh: bool = False
) -> CachedSnapshot:
    """Snapshot del schema desde la caché o leído en el subproceso (y cacheado)."""
    if not refresh:
        cached = _load(db, connection.id, schema)
        if cached is not None:
            return cached
    params = _conn_params(db, connection, settings)
    with probe_slot():
        data = _value(
            metadata.read_snapshot(connection.db_type, params, schema, timeout=settings.metadata_timeout_seconds)
        )
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    payload = zlib.compress(raw, level=6)
    now = utcnow()
    db.merge(
        MetadataCache(connection_id=connection.id, schema=schema, fetched_at=now, size_bytes=len(raw), payload=payload)
    )
    db.commit()
    return CachedSnapshot(dict(data), now, len(raw))


def invalidate(db: Session, connection: Connection, schema: str | None = None) -> None:
    query = delete(MetadataCache).where(MetadataCache.connection_id == connection.id)
    if schema is not None:
        query = query.where(MetadataCache.schema == schema)
    db.execute(query)
    db.commit()


def summary(snapshot: CachedSnapshot) -> dict[str, Any]:
    """Árbol del schema: tablas (con nº de columnas), vistas y rutinas."""
    data = snapshot.data
    columns: dict[str, list[Any]] = data.get("columns", {})
    return {
        "engine": data.get("engine"),
        "schema": data.get("schema"),
        "database": data.get("database"),
        "fetched_at": snapshot.fetched_at,
        "size_bytes": snapshot.size_bytes,
        "tables": [
            {"name": t["name"], "comment": t.get("comment"), "columns": len(columns.get(t["name"], []))}
            for t in data.get("tables", [])
        ],
        "views": [
            {"name": v["name"], "comment": v.get("comment"), "materialized": bool(v.get("materialized"))}
            for v in data.get("views", [])
        ],
        "routines": [
            {
                "name": r["name"],
                "routine_type": r.get("routine_type"),
                "signature": r.get("signature") or "",
                "return_type": r.get("return_type"),
            }
            for r in data.get("routines", [])
        ],
    }


def table_detail(snapshot: CachedSnapshot, table: str) -> dict[str, Any]:
    """Columnas, claves, índices y FK salientes y entrantes de ``table``.

    Raises:
        ObjectNotFoundError: No está en el snapshot.
    """
    data = snapshot.data
    match = next((t for t in data.get("tables", []) if t["name"] == table), None)
    if match is None:
        raise ObjectNotFoundError(f"La tabla «{table}» no está en el schema (prueba a refrescar).")
    fks = data.get("foreign_keys", [])
    return {
        "name": table,
        "comment": match.get("comment"),
        "fetched_at": snapshot.fetched_at,
        "columns": data.get("columns", {}).get(table, []),
        "primary_key": data.get("primary_keys", {}).get(table),
        "uniques": data.get("uniques", {}).get(table, []),
        "checks": data.get("checks", {}).get(table, []),
        "indexes": data.get("indexes", {}).get(table, []),
        "identity": data.get("identity", {}).get(table, []),
        "foreign_keys": [fk for fk in fks if fk.get("table") == table],
        "referenced_by": [fk for fk in fks if fk.get("ref_table") == table],
    }


def object_ddl(
    db: Session, connection: Connection, schema: str, kind: ObjectKind, name: str, settings: Settings
) -> str:
    params = _conn_params(db, connection, settings)
    with probe_slot():
        return str(
            _value(
                metadata.read_ddl(
                    connection.db_type, params, schema, kind, name, timeout=settings.metadata_timeout_seconds
                )
            )
            or ""
        )


def cached_schemas(db: Session, connection: Connection) -> list[str]:
    return list(db.scalars(select(MetadataCache.schema).where(MetadataCache.connection_id == connection.id)))
