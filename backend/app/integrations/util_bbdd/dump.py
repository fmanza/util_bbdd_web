"""Volcado de datos con util_bbdd (Fase 8, ADR-009); se ejecuta dentro del subproceso del job.

- ``DumpOrchestrator(DumpConfig(...)).run() -> DumpResult``: copia filas tabla a tabla en orden de FK, con las
  constraints del destino **desactivadas** durante la carga (SQL Server, Oracle, PostgreSQL, MySQL/MariaDB; SQLite no
  las toca). Transaccional por tabla, *best-effort* entre tablas.
- util_bbdd no ofrece vista previa pública (G29): ``preview`` replica con el ``Inspector`` de SQLAlchemy el orden de
  ``util_bbdd.dump._fk_graph.topological_sort`` (cola en el orden de las tablas, dependientes ordenados, ciclos al
  final) y añade filas, columnas y avisos.
- ``DumpConfig.truncate_target`` es ``True`` por defecto (G30): la web lo pasa siempre explícito.
- Con destino Oracle, ``on_error="isolate"`` no aparta las filas con PK duplicada: la tabla falla (G32, aviso
  ``isolate_oracle`` en la vista previa).
- SQLite → SQLite falla en columnas ``DATE``/``DATETIME`` del destino si el origen guarda la fecha como texto (lo normal
  en SQLite): ``TypeError: SQLite Date type only accepts Python date objects`` (G33, aviso ``sqlite_dates``).
- ``TableDumpResult.error_msg`` y ``ConstraintResult.error_msg`` traen el texto de SQLAlchemy **con los parámetros**
  (filas del origen): se guarda solo su primera línea (``_engine_message``) y sin los valores que algunos motores
  ponen en ella (``redact_values``, G34).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from app.integrations.util_bbdd.compare import resolve_schema
from app.integrations.util_bbdd.sql import _engine_message

#: Motores cuyas constraints gestiona util_bbdd durante la carga (``dump._constraints._SUPPORTED_DIALECTS``).
CONSTRAINT_ENGINES: Final = frozenset({"sqlserver", "mariadb", "mysql", "oracle", "postgresql"})
RESULT_FILE: Final = "result.json"
AUDIT_FILE: Final = "volcado.jsonl"
REJECTS_FILE: Final = "rechazos.csv"
REPORT_FILE: Final = "volcado.xlsx"


class UnknownTablesError(LookupError):
    """Tablas pedidas que no existen en el origen."""

    def __init__(self, tables: list[str]) -> None:
        super().__init__(", ".join(tables))
        self.tables = tables


class PreviewChangedError(RuntimeError):
    """La estructura del volcado (tablas, columnas, orden) cambió desde la vista previa."""


@dataclass(frozen=True)
class Endpoint:
    """Un lado del volcado: motor, ``conn_params`` preparados y schema."""

    db_type: str
    conn_params: dict[str, Any]
    schema: str | None


@dataclass(frozen=True)
class DumpOptions:
    """Opciones del volcado que expone el formulario (el resto, valores por defecto de util_bbdd)."""

    tables: tuple[str, ...] = ()
    truncate_target: bool = False
    on_error: Literal["raise", "isolate"] = "raise"
    max_rejects: int | None = None
    chunk_size: int = 5000
    max_parallel_tables: int = 1
    manage_indexes: Literal["none", "secondary"] = "none"
    sync_pk_sequences: bool = True


def parse_tables(raw: str | None) -> tuple[str, ...]:
    """``"a, b ,c"`` → ``("a", "b", "c")``; vacío = todas las tablas."""
    return tuple(t.strip() for t in (raw or "").split(",") if t.strip())


# --- vista previa ------------------------------------------------------------------------------------------------


def load_order(tables: list[str], referred: dict[str, list[str]]) -> tuple[list[str], list[list[str]]]:
    """Orden de carga y ciclos, como ``util_bbdd.dump._fk_graph.topological_sort``.

    Args:
        tables: Tablas en el orden en que util_bbdd las recibe.
        referred: Tablas a las que apunta cada tabla por FK.
    """
    tables_set = set(tables)
    dependents: dict[str, set[str]] = {t: set() for t in tables}
    in_degree = dict.fromkeys(tables, 0)
    for table in tables:
        for ref in referred.get(table, []):
            if ref and ref != table and ref in tables_set and table not in dependents[ref]:
                dependents[ref].add(table)
                in_degree[table] += 1
    queue = deque(t for t in tables if in_degree[t] == 0)
    ordered: list[str] = []
    while queue:
        node = queue.popleft()
        ordered.append(node)
        for dep in sorted(dependents[node]):
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)
    done = set(ordered)
    cycle_tables = [t for t in tables if t not in done]
    return ordered + cycle_tables, _components(cycle_tables, dependents)


def _components(cycle_tables: list[str], dependents: dict[str, set[str]]) -> list[list[str]]:
    cycle_set = set(cycle_tables)
    adjacent: dict[str, set[str]] = {t: set() for t in cycle_tables}
    for node in cycle_tables:
        for dep in dependents[node]:
            if dep in cycle_set:
                adjacent[node].add(dep)
                adjacent[dep].add(node)
    seen: set[str] = set()
    components: list[list[str]] = []
    for start in cycle_tables:
        if start in seen:
            continue
        component: list[str] = []
        queue = deque([start])
        while queue:
            node = queue.popleft()
            if node in seen:
                continue
            seen.add(node)
            component.append(node)
            queue.extend(n for n in adjacent[node] if n not in seen)
        components.append(component)
    return components


def _count(engine: Any, table: str, schema: str | None) -> int:
    from sqlalchemy import func, select
    from sqlalchemy import table as sa_table

    with engine.connect() as connection:
        return int(connection.execute(select(func.count()).select_from(sa_table(table, schema=schema))).scalar_one())


def _is_date(column_type: Any) -> bool:
    from sqlalchemy import Date, DateTime

    return isinstance(column_type, Date | DateTime)


def _required(column: Any, source_columns: set[str]) -> bool:
    """Columna del destino que el origen no tiene y que no admite nulos ni tiene valor por defecto: la carga fallará."""
    return (
        column["name"].lower() not in source_columns
        and not column.get("nullable", True)
        and column.get("default") is None
        and column.get("autoincrement") is not True
    )


def _source_tables(inspector: Any, schema: str | None, wanted: tuple[str, ...]) -> list[str]:
    """Tablas del origen (nombres del catálogo); si se piden, ordenadas como hace util_bbdd y sin distinguir caja."""
    available = list(inspector.get_table_names(schema=schema))
    if not wanted:
        return available
    by_lower = {name.lower(): name for name in available}
    missing = [t for t in wanted if t.lower() not in by_lower]
    if missing:
        raise UnknownTablesError(missing)
    return sorted({by_lower[t.lower()] for t in wanted})


def build_preview(source: Endpoint, target: Endpoint, options: DumpOptions) -> dict[str, Any]:
    """Vista previa (modo seco, solo lectura): orden por FK, ciclos, filas, columnas y avisos por tabla.

    Raises:
        UnknownTablesError: Alguna tabla pedida no existe en el origen.
        SchemaNotFoundError: El schema no existe en un lado.
    """
    from sqlalchemy import inspect
    from util_bbdd import SyncDatabaseManager

    with (
        SyncDatabaseManager(source.db_type, source.conn_params, use_pool=False) as source_manager,
        SyncDatabaseManager(target.db_type, target.conn_params, use_pool=False) as target_manager,
    ):
        source_engine = source_manager.get_sqlalchemy_engine()
        target_engine = target_manager.get_sqlalchemy_engine()
        src_inspector = inspect(source_engine)
        dst_inspector = inspect(target_engine)
        src_schema = _resolve(src_inspector, "source", source.schema)
        dst_schema = _resolve(dst_inspector, "target", target.schema)
        tables = _source_tables(src_inspector, src_schema, options.tables)
        referred = {
            t: [fk.get("referred_table") or "" for fk in src_inspector.get_foreign_keys(t, schema=src_schema)]
            for t in tables
        }
        order, cycles = load_order(tables, referred)
        in_cycle = {t for component in cycles for t in component}
        dst_by_lower = {name.lower(): name for name in dst_inspector.get_table_names(schema=dst_schema)}
        rows: list[dict[str, Any]] = []
        for position, table in enumerate(order):
            target_name = dst_by_lower.get(table.lower())
            src_cols = [c["name"] for c in src_inspector.get_columns(table, schema=src_schema)]
            entry: dict[str, Any] = {
                "table": table,
                "target_table": target_name,
                "position": position,
                "in_cycle": table in in_cycle,
                "source_rows": _count(source_engine, table, src_schema),
                "target_rows": None,
                "skipped_columns": [],
                "missing_target_columns": [],
                "outside_references": sorted({r for r in referred[table] if r and r not in set(tables)}),
                "date_columns": [],
            }
            if target_name is not None:
                dst_cols = dst_inspector.get_columns(target_name, schema=dst_schema)
                dst_names = {c["name"].lower() for c in dst_cols}
                src_lower = {c.lower() for c in src_cols}
                entry["target_rows"] = _count(target_engine, target_name, dst_schema)
                entry["skipped_columns"] = [c for c in src_cols if c.lower() not in dst_names]
                entry["missing_target_columns"] = [c["name"] for c in dst_cols if _required(c, src_lower)]
                if source.db_type == target.db_type == "sqlite":
                    entry["date_columns"] = [c["name"] for c in dst_cols if _is_date(c["type"])]
            rows.append(entry)
    data = {
        "source_engine": source.db_type,
        "target_engine": target.db_type,
        "source_schema": src_schema,
        "target_schema": dst_schema,
        "truncate_target": options.truncate_target,
        "constraints_managed": target.db_type in CONSTRAINT_ENGINES,
        "warnings": _warnings(target, options) + (["sqlite_dates"] if any(r["date_columns"] for r in rows) else []),
        "tables": rows,
        "cycles": cycles,
        "load_order": order,
    }
    data["structure_hash"] = structure_hash(data)
    return data


def _warnings(target: Endpoint, options: DumpOptions) -> list[str]:
    """Avisos generales del volcado (códigos estables para la interfaz)."""
    warnings: list[str] = []
    if options.on_error == "isolate" and target.db_type == "oracle":
        warnings.append("isolate_oracle")  # G32: util_bbdd no aparta la PK duplicada en Oracle
    return warnings


def structure_hash(preview: dict[str, Any]) -> str:
    """Huella de lo que se va a cargar: tablas, destino, columnas omitidas y orden (no las filas, que cambian)."""
    shape = [
        (t["table"], t["target_table"], t["skipped_columns"], t["missing_target_columns"], t["position"])
        for t in preview["tables"]
    ]
    payload = json.dumps([shape, preview["cycles"], preview["source_schema"], preview["target_schema"]])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _resolve(inspector: Any, side: str, schema: str | None) -> str | None:
    if not schema:
        return None
    return resolve_schema(side, schema, list(inspector.get_schema_names()), inspector.dialect)


# --- volcado -----------------------------------------------------------------------------------------------------


def run_dump(
    source: Endpoint,
    target: Endpoint,
    *,
    options: DumpOptions,
    expected_structure: str,
    outputs_dir: Path,
    work_dir: Path,
) -> dict[str, Any]:
    """Recalcula la vista previa, exige la misma estructura y ejecuta ``DumpOrchestrator``.

    Returns:
        Resultado serializable (``result.json``): por tabla, constraints, contadores PK, orden y ciclos.

    Raises:
        PreviewChangedError: La estructura cambió desde la vista previa revisada.
    """
    from util_bbdd.audit import JsonLinesAuditSink

    preview = build_preview(source, target, options)
    if preview["structure_hash"] != expected_structure:
        raise PreviewChangedError(preview["structure_hash"])
    rejects = outputs_dir / "rejects" / REJECTS_FILE
    audit_path = outputs_dir / "audit" / AUDIT_FILE
    for folder in (rejects.parent, audit_path.parent, work_dir):
        folder.mkdir(parents=True, exist_ok=True)
    sink = JsonLinesAuditSink(audit_path)
    try:
        return _orchestrate(source, target, preview, options, sink, rejects, outputs_dir, work_dir)
    finally:
        sink.close()
        shutil.rmtree(work_dir, ignore_errors=True)


def _orchestrate(
    source: Endpoint,
    target: Endpoint,
    preview: dict[str, Any],
    options: DumpOptions,
    sink: Any,
    rejects: Path,
    outputs_dir: Path,
    work_dir: Path,
) -> dict[str, Any]:
    """``DumpOrchestrator`` con la configuración de la vista previa; mueve el Excel a ``outputs/excel``."""
    from util_bbdd import SyncDatabaseManager
    from util_bbdd.dump import DumpConfig, DumpOrchestrator, DumpReportError

    with (
        SyncDatabaseManager(source.db_type, source.conn_params, use_pool=False) as source_manager,
        SyncDatabaseManager(target.db_type, target.conn_params, use_pool=False) as target_manager,
    ):
        config = DumpConfig(
            source_engine=source_manager.get_sqlalchemy_engine(),
            target_engine=target_manager.get_sqlalchemy_engine(),
            source_schema=preview["source_schema"],
            target_schema=preview["target_schema"],
            tables=[t["table"] for t in preview["tables"]] if options.tables else None,
            chunk_size=options.chunk_size,
            output_dir=work_dir,
            truncate_target=options.truncate_target,
            max_parallel_tables=options.max_parallel_tables,
            manage_indexes="secondary" if options.manage_indexes == "secondary" else False,
            sync_pk_sequences=options.sync_pk_sequences,
            on_error=options.on_error,
            rejects_csv_path=rejects if options.on_error == "isolate" else None,
            max_rejects=options.max_rejects if options.on_error == "isolate" else None,
            audit_sink=sink,
        )
        try:
            result = DumpOrchestrator(config).run()
            report_ok = True
        except DumpReportError as exc:  # la carga terminó; solo falló el Excel
            result, report_ok = exc.result, False
    if report_ok and result.report.exists():
        excel = outputs_dir / "excel" / REPORT_FILE
        excel.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(result.report), str(excel))
    return result_to_dict(result, report_ok)


#: Valores de filas que algunos motores ponen en la primera línea del error (G34): MySQL/MariaDB
#: ``Duplicate entry 'x' for key``/``Incorrect integer value: 'x'``, SQL Server ``duplicate key value is (x)`` y
#: ``converting the varchar value 'x'``. Se cambian por ``…``; los nombres de clave o columna se conservan.
_QUOTED_VALUE = re.compile(r"\b(entry|value:?)\s+'[^']*'", re.IGNORECASE)
_PAREN_VALUE = re.compile(r"\b(value is)\s+\([^)]*\)", re.IGNORECASE)


def redact_values(message: str) -> str:
    """Mensaje del motor sin los valores de las filas que lo provocaron."""
    return _PAREN_VALUE.sub(r"\1 (…)", _QUOTED_VALUE.sub(r"\1 '…'", message))


def _clean(message: str) -> str | None:
    return redact_values(_engine_message(RuntimeError(message))) if message else None


def result_to_dict(result: Any, report_ok: bool) -> dict[str, Any]:
    """``DumpResult`` serializable y sin datos de filas en los mensajes de error."""
    return {
        "load_order": list(result.load_order),
        "cycles": [list(c) for c in result.cycles_detected],
        "report": report_ok,
        "tables": [
            {
                "table": t.table_name,
                "status": t.status,
                "source_rows": t.source_rows,
                "target_rows_before": t.target_rows_before,
                "target_rows_after": t.target_rows_after,
                "rows_rejected": t.rows_rejected,
                "skipped_columns": list(t.skipped_columns),
                "position": t.load_order_position,
                "in_cycle": t.in_cycle,
                "error": _clean(t.error_msg),
            }
            for t in result.table_results
        ],
        "constraints": [
            {"table": c.table_name, "constraint": c.constraint_name, "status": c.status, "error": _clean(c.error_msg)}
            for c in result.constraint_results
        ],
        "pk_sync": [
            {
                "table": getattr(p, "table_name", ""),
                "status": str(getattr(p, "status", "")),
                "error": _clean(str(getattr(p, "error_msg", "") or "")),
            }
            for p in (result.pk_sync_results or [])
        ],
    }
