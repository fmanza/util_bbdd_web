"""Volcado de datos con util_bbdd (Fase 8, ADR-009); se ejecuta dentro del subproceso del job.

- ``DumpOrchestrator(DumpConfig(...)).run() -> DumpResult``: copia filas tabla a tabla en orden de FK, con las
  constraints del destino **desactivadas** durante la carga (SQL Server, Oracle, PostgreSQL, MySQL/MariaDB; SQLite no
  las toca). Transaccional por tabla, *best-effort* entre tablas.
- ``build_preview`` toma de ``DumpOrchestrator.plan()`` (util_bbdd 4.4.0, G29) el orden de carga, los ciclos y las
  columnas por tabla, con el mismo ``DumpConfig`` que el volcado (``_config``), y añade los recuentos de filas.
- ``DumpConfig.truncate_target`` es ``True`` por defecto (G30): la web lo pasa siempre explícito.
- Desde util_bbdd 4.4.0, ``on_error="isolate"`` aparta también la PK duplicada en Oracle (G32) y SQLite → SQLite carga
  las fechas guardadas como texto ISO (G33): la vista previa ya no avisa de ninguno de los dos.
- ``TableDumpResult.error_msg`` y ``ConstraintResult.error_msg`` llegan saneados desde util_bbdd 4.4.0 (G34); la web
  se sigue quedando con la primera línea y enmascara los valores conocidos (``_clean``, ``redact_values``) como
  defensa, que además cubre el ``error_msg`` de los contadores PK, que util_bbdd no sanea.
- Progreso por tabla y por lote y cancelación **entre lotes** (``run(on_progress=, cancel_token=)``, util_bbdd 4.4.0,
  G1) con ``DumpProgress``: util_bbdd deshace la tabla en curso, reactiva constraints e índices y lanza
  ``OperationCancelledError`` sin ``DumpResult``; ``result.json`` lleva entonces ``cancelled`` y las tablas terminadas.
- Si alguna constraint no se reactiva o el proceso muere, queda ``constraints_journal.json`` en ``output_dir`` (la
  carpeta ``work`` del run, que entonces se conserva) y ``restore_constraints`` las reactiva después (G31).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from app.integrations.util_bbdd.compare import resolve_schema
from app.integrations.util_bbdd.progress import RunProgress, is_cancellation
from app.integrations.util_bbdd.sql import MAX_ENGINE_MESSAGE

#: Diario de constraints de util_bbdd en ``DumpConfig.output_dir`` (4.4.0, G31; solo SQL Server, PostgreSQL y Oracle).
JOURNAL_FILE: Final = "constraints_journal.json"
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


def _config(
    source_engine: Any,
    target_engine: Any,
    source_schema: str | None,
    target_schema: str | None,
    tables: list[str],
    options: DumpOptions,
    rejects: Path,
    **extra: Any,
) -> Any:
    """``DumpConfig`` del volcado; la vista previa (``plan()``) y el volcado (``run()``) usan el mismo.

    ``rejects`` es el CSV de rechazos con ``on_error="isolate"`` (``DumpConfig`` lo exige; ``plan()`` no lo escribe).
    """
    from util_bbdd.dump import DumpConfig

    return DumpConfig(
        source_engine=source_engine,
        target_engine=target_engine,
        source_schema=source_schema,
        target_schema=target_schema,
        tables=tables if options.tables else None,
        chunk_size=options.chunk_size,
        truncate_target=options.truncate_target,
        max_parallel_tables=options.max_parallel_tables,
        manage_indexes="secondary" if options.manage_indexes == "secondary" else False,
        sync_pk_sequences=options.sync_pk_sequences,
        on_error=options.on_error,
        rejects_csv_path=rejects if options.on_error == "isolate" else None,
        max_rejects=options.max_rejects if options.on_error == "isolate" else None,
        **extra,
    )


def _count(engine: Any, table: str, schema: str | None) -> int:
    from sqlalchemy import func, select
    from sqlalchemy import table as sa_table

    with engine.connect() as connection:
        return int(connection.execute(select(func.count()).select_from(sa_table(table, schema=schema))).scalar_one())


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
    from util_bbdd.dump import DumpOrchestrator

    with (
        SyncDatabaseManager(source.db_type, source.conn_params, use_pool=False) as source_manager,
        SyncDatabaseManager(target.db_type, target.conn_params, use_pool=False) as target_manager,
    ):
        source_engine = source_manager.get_sqlalchemy_engine()
        target_engine = target_manager.get_sqlalchemy_engine()
        src_inspector = inspect(source_engine)
        src_schema = _resolve(src_inspector, "source", source.schema)
        dst_schema = _resolve(inspect(target_engine), "target", target.schema)
        tables = _source_tables(src_inspector, src_schema, options.tables)
        config = _config(source_engine, target_engine, src_schema, dst_schema, tables, options, Path(REJECTS_FILE))
        plan = DumpOrchestrator(config).plan()
        in_cycle = {t for component in plan.cycles for t in component}
        rows: list[dict[str, Any]] = []
        # Posición en ``load_order``, también para las tablas sin destino (util_bbdd les da -1).
        for position, table in enumerate(plan.tables):
            entry: dict[str, Any] = {
                "table": table.table_name,
                "target_table": table.target_table,
                "position": position,
                "in_cycle": table.table_name in in_cycle,
                "source_rows": _count(source_engine, table.table_name, src_schema),
                "target_rows": None,
                "skipped_columns": list(table.skipped_columns),
                "missing_target_columns": list(table.required_target_columns),
                "outside_references": list(table.outside_references),
            }
            if table.target_table is not None:
                entry["target_rows"] = _count(target_engine, table.target_table, dst_schema)
            rows.append(entry)
    data = {
        "source_engine": source.db_type,
        "target_engine": target.db_type,
        "source_schema": src_schema,
        "target_schema": dst_schema,
        "truncate_target": options.truncate_target,
        "constraints_managed": plan.constraints_managed,
        "tables": rows,
        "cycles": [list(c) for c in plan.cycles],
        "load_order": list(plan.load_order),
    }
    data["structure_hash"] = structure_hash(data)
    return data


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


class DumpProgress(RunProgress):
    """``on_progress`` del volcado (operación ``dump``): fases ``tables`` (una por tabla terminada) y ``rows`` (una por
    lote, con el ``COUNT(*)`` del origen como total).

    El porcentaje son las tablas terminadas más la parte escrita de la tabla del último lote; ``completed`` guarda las
    tablas terminadas, que son las que quedan cargadas si se cancela.
    """

    def __init__(
        self,
        report: Callable[[str, int | None], None],
        cancel_requested: Callable[[], bool],
        *,
        poll_seconds: float = 2.0,
    ) -> None:
        super().__init__(report, cancel_requested, ("tables", "rows"), poll_seconds=poll_seconds)
        self.completed: list[str] = []
        self._tables = 0

    def __call__(self, event: Any) -> None:
        if event.phase == "tables":
            self._tables = event.total or self._tables
            if event.current and event.message:
                self.completed.append(event.message)
        super().__call__(event)

    def percent(self, event: Any) -> int | None:
        if not self._tables:
            return None
        done = len(self.completed) + ((event.fraction or 0.0) if event.phase == "rows" else 0.0)
        return min(99, int(done * 100 / self._tables))

    def message(self, event: Any) -> str:
        tables = f"{len(self.completed)} de {self._tables} tablas"
        if event.phase == "rows" and event.message:
            rows = f"{event.current} de {event.total}" if event.total is not None else str(event.current)
            return f"Cargando {event.message}: {rows} filas ({tables})"
        return f"Volcado: {tables}"


def cancelled_result(preview: dict[str, Any], completed: list[str]) -> dict[str, Any]:
    """``result.json`` de un volcado cancelado: util_bbdd no devuelve ``DumpResult``; constan las tablas terminadas."""
    return {
        "load_order": preview["load_order"],
        "cycles": preview["cycles"],
        "report": False,
        "tables": [],
        "constraints": [],
        "pk_sync": [],
        "cancelled": True,
        "completed_tables": list(completed),
    }


def run_dump(
    source: Endpoint,
    target: Endpoint,
    *,
    options: DumpOptions,
    expected_structure: str,
    outputs_dir: Path,
    work_dir: Path,
    progress: DumpProgress | None = None,
) -> dict[str, Any]:
    """Recalcula la vista previa, exige la misma estructura y ejecuta ``DumpOrchestrator``.

    Returns:
        Resultado serializable (``result.json``): por tabla, constraints, contadores PK, orden y ciclos; si se canceló
        entre lotes (``progress.token``), ``cancelled_result``.

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
        return _orchestrate(source, target, preview, options, sink, rejects, outputs_dir, work_dir, progress)
    finally:
        sink.close()
        # Con el diario pendiente (alguna constraint no se reactivó) la carpeta se conserva para restaurarlas.
        if not (work_dir / JOURNAL_FILE).exists():
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
    progress: DumpProgress | None,
) -> dict[str, Any]:
    """``DumpOrchestrator`` con la configuración de la vista previa; mueve el Excel a ``outputs/excel``."""
    from util_bbdd import SyncDatabaseManager
    from util_bbdd.dump import DumpOrchestrator, DumpReportError

    with (
        SyncDatabaseManager(source.db_type, source.conn_params, use_pool=False) as source_manager,
        SyncDatabaseManager(target.db_type, target.conn_params, use_pool=False) as target_manager,
    ):
        config = _config(
            source_manager.get_sqlalchemy_engine(),
            target_manager.get_sqlalchemy_engine(),
            preview["source_schema"],
            preview["target_schema"],
            [t["table"] for t in preview["tables"]],
            options,
            rejects,
            output_dir=work_dir,
            audit_sink=sink,
        )
        try:
            result = DumpOrchestrator(config).run(
                on_progress=progress, cancel_token=progress.token if progress is not None else None
            )
            report_ok = True
        except DumpReportError as exc:  # la carga terminó; solo falló el Excel
            result, report_ok = exc.result, False
        except Exception as exc:
            if not is_cancellation(exc):
                raise
            return cancelled_result(preview, progress.completed if progress is not None else [])
    if report_ok and result.report.exists():
        excel = outputs_dir / "excel" / REPORT_FILE
        excel.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(result.report), str(excel))
    return result_to_dict(result, report_ok)


def restore_constraints(target: Endpoint, journal: Path) -> dict[str, Any]:
    """Reactiva lo que un volcado interrumpido dejó desactivado (``util_bbdd.dump.restore_constraints``, G31).

    Es idempotente y util_bbdd borra el diario si todo se reactiva.

    Returns:
        ``constraints`` (por tabla o constraint, con el error saneado) y ``pending`` (el diario sigue: alguna falló).

    Raises:
        ValueError: El fichero no es un diario válido o es de otro motor.
    """
    from util_bbdd import SyncDatabaseManager
    from util_bbdd.dump import restore_constraints as restore

    with SyncDatabaseManager(target.db_type, target.conn_params, use_pool=False) as manager:
        results = restore(manager.get_sqlalchemy_engine(), journal)
    return {
        "constraints": [
            {"table": r.table_name, "constraint": r.constraint_name, "status": r.status, "error": _clean(r.error_msg)}
            for r in results
        ],
        "pending": journal.exists(),
    }


#: Valores de filas que algunos motores ponen en la primera línea del error (G34): MySQL/MariaDB
#: ``Duplicate entry 'x' for key``/``Incorrect integer value: 'x'``, SQL Server ``duplicate key value is (x)``,
#: ``converting the varchar value 'x'`` y ``Truncated value: 'x'``, y PostgreSQL ``invalid input syntax for type
#: integer: "x"``. Se cambian por ``…``; los nombres de clave o columna se conservan.
_QUOTED_VALUE = re.compile(r"\b(entry|value:?)\s+'[^']*'", re.IGNORECASE)
_PAREN_VALUE = re.compile(r"\b(value is)\s+\([^)]*\)", re.IGNORECASE)
_DOUBLE_QUOTED_VALUE = re.compile(r'\b(invalid input (?:syntax|value) for [^:]+:)\s*"[^"]*"', re.IGNORECASE)
_URL = re.compile(r"\b[a-z][a-z0-9+]*://\S+")


def redact_values(message: str) -> str:
    """Mensaje del motor sin los valores de las filas que lo provocaron."""
    message = _DOUBLE_QUOTED_VALUE.sub(r'\1 "…"', message)
    return _PAREN_VALUE.sub(r"\1 (…)", _QUOTED_VALUE.sub(r"\1 '…'", message))


def _clean(message: str) -> str | None:
    """Mensaje de error para ``result.json``, sin datos de filas (G34).

    Desde util_bbdd 4.4.0 el ``error_msg`` de tablas y constraints ya llega saneado (primera línea, sin sentencia,
    parámetros ni URL y con los valores enmascarados); el de los contadores PK, que viene de ``bulk``, no. Por eso se
    sigue quedando con la primera línea, sin ``[SQL: …]`` ni URL, y aplicando ``redact_values`` a todos (con lo ya
    saneado no cambia nada).
    """
    lines = message.strip().splitlines()
    if not lines:
        return None
    line = lines[0].split("[SQL:")[0].split("(Background on this error")[0]
    return redact_values(_URL.sub("[url]", line).strip()[:MAX_ENGINE_MESSAGE]) or None


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
