"""Carga bulk desde fichero con ``BulkCrud`` de util_bbdd (Fase 9, ADR-010); se ejecuta en el subproceso del job.

- ``bulk_insert|update|delete_from_df(df, tabla, dry_run=True, path_sql=dir)`` **escribe el SQL sin ejecutarlo**
  (una sentencia por fila, con los valores): es el modo seco y el artefacto ``outputs/sql/carga_<op>.sql``. Sin
  ``dry_run`` ni ``generar_sql`` util_bbdd ejecuta desde 5.0.0 (antes escribía el SQL sin ejecutar, G35): la web pasa
  siempre ``dry_run`` explícito, ``False`` al aplicar.
- Con ``ParallelOptions`` y un plan de más de un hilo la operación deja de ser atómica (una transacción por
  partición, G36). ``ParallelPlan.atomic`` (util_bbdd 4.5.0) lo dice en la vista previa; al cargar sin
  ``accept_non_atomic`` se pide ``require_atomic=True``, que fuerza un hilo aunque el plan haya cambiado.
- El fichero lo lee la web (``domain/uploads/files.py``) y llega aquí como ``DataFrame``.
- Progreso por lote y cancelación **entre lotes** (``on_progress``/``cancel_token``, util_bbdd 4.5.0, G1) con
  ``RunProgress``: util_bbdd deshace la transacción en curso y lanza ``OperationCancelledError``. En una carga de una
  sola transacción eso deshace **toda** la operación; en paralelo, las particiones terminadas quedan. ``result.json``
  lleva entonces ``cancelled``.
- ``last_operation_rows_committed`` (fiable desde util_bbdd 4.5.0, G37) da las filas **enviadas** y confirmadas
  (también las apartadas; un UPDATE o DELETE de una clave que no existe cuenta): es la cifra principal del resultado.
  El recuento del destino antes y después se mantiene como verificación (``verify``).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

from app.integrations.util_bbdd.compare import resolve_schema
from app.integrations.util_bbdd.dump import redact_values
from app.integrations.util_bbdd.progress import RunProgress, is_cancellation
from app.integrations.util_bbdd.sql import _engine_message

Operation = Literal["insert", "update", "delete"]
SAMPLE_ROWS: Final = 20
_PK_BATCH: Final = 500
_COMPOSITE_BATCH: Final = 200  # SQL Server admite 2100 parámetros por sentencia
SQL_FILE: Final = "carga_{op}.sql"
REJECTS_FILE: Final = "rechazos.csv"
AUDIT_FILE: Final = "carga.jsonl"


class StructureChangedError(RuntimeError):
    """La tabla destino o el mapeo resuelto cambiaron desde la vista previa."""


class MatchesChangedError(RuntimeError):
    """Las filas del destino que coinciden por PK ya no son las confirmadas (update/delete)."""


@dataclass(frozen=True)
class Target:
    """Conexión destino: motor, ``conn_params`` preparados y schema."""

    db_type: str
    conn_params: dict[str, Any]
    schema: str | None


@dataclass(frozen=True)
class BulkOptions:
    """Qué se carga y cómo (las del asistente)."""

    table: str
    operation: Operation
    mapping: dict[str, str] = field(default_factory=dict)
    on_error: Literal["raise", "isolate"] = "raise"
    max_rejects: int | None = None
    parallel: bool = False
    chunk_size: int | None = None
    #: Al cargar sin aceptar que no sea atómica: util_bbdd fuerza un hilo (``ParallelOptions(require_atomic=True)``).
    require_atomic: bool = False


def _parallel(options: BulkOptions) -> Any:
    from util_bbdd.bulk import ParallelOptions

    return ParallelOptions(mode="auto", require_atomic=options.require_atomic) if options.parallel else None


def _clean(message: str) -> str:
    return redact_values(_engine_message(RuntimeError(message)))


def _qualified(schema: str | None, table: str) -> str:
    return f"{schema}.{table}" if schema else table


def _resolve_mapping(frame_columns: list[str], table_columns: list[str], mapping: dict[str, str]) -> dict[str, Any]:
    """Columnas del fichero → columnas de la tabla (nombre real). Sin mapeo explícito, por nombre sin distinguir caja."""
    by_lower = {c.lower(): c for c in table_columns}
    resolved: dict[str, str] = {}
    unknown: list[str] = []
    missing_in_file = [c for c in mapping if c not in frame_columns]
    pairs = mapping.items() if mapping else ((c, c) for c in frame_columns)
    for source, target in pairs:
        if source not in frame_columns:
            continue
        real = by_lower.get(target.lower())
        if real is None:
            if mapping:
                unknown.append(target)
            continue
        resolved[source] = real
    ignored = [c for c in frame_columns if c not in resolved]
    return {"resolved": resolved, "unknown": unknown, "ignored": ignored, "missing_in_file": missing_in_file}


def _required_columns(table: Any) -> list[str]:
    """Columnas obligatorias en un INSERT: no nulas, sin valor por defecto ni autoincremento."""
    required: list[str] = []
    for column in table.columns:
        auto = column.autoincrement is True or (column.primary_key and column.autoincrement == "auto"
                                                and len(table.primary_key.columns) == 1)  # fmt: skip
        if not column.nullable and column.server_default is None and column.default is None and not auto:
            required.append(column.name)
    return required


def _count_matches(engine: Any, table: Any, keys: list[tuple[Any, ...]], pk: list[str]) -> int:
    """Filas **distintas** del destino cuya PK está en ``keys`` (por lotes; ``OR`` de ``AND`` si la PK es compuesta).

    Las claves se deduplican antes de partir en lotes: una clave repetida en el fichero en lotes distintos contaría
    la misma fila varias veces.
    """
    from sqlalchemy import and_, func, or_, select

    keys = list(dict.fromkeys(keys))
    if not keys:
        return 0
    columns = [table.c[name] for name in pk]
    total = 0
    batch = _PK_BATCH if len(pk) == 1 else _COMPOSITE_BATCH
    with engine.connect() as connection:
        for start in range(0, len(keys), batch):
            part = keys[start : start + batch]
            if len(pk) == 1:
                condition = columns[0].in_([k[0] for k in part])
            else:
                condition = or_(*(and_(*(c == v for c, v in zip(columns, k, strict=True))) for k in part))
            total += int(connection.execute(select(func.count()).select_from(table).where(condition)).scalar_one())
    return total


def _count(engine: Any, table: Any) -> int:
    from sqlalchemy import func, select

    with engine.connect() as connection:
        return int(connection.execute(select(func.count()).select_from(table)).scalar_one())


def _frame_records(frame: Any, limit: int) -> list[list[str | None]]:
    rows: list[list[str | None]] = []
    for row in frame.head(limit).itertuples(index=False):
        rows.append([None if v != v else str(v)[:200] for v in row])  # NaN != NaN
    return rows


def _prepare(target: Target, frame: Any, options: BulkOptions) -> dict[str, Any]:
    """Resuelve el mapeo del ``frame`` contra la tabla y valida. Devuelve lo que necesitan vista previa y carga."""
    from sqlalchemy import inspect
    from util_bbdd import SyncDatabaseManager
    from util_bbdd.bulk import BulkCrud

    manager = SyncDatabaseManager(target.db_type, target.conn_params, use_pool=False)
    engine = manager.get_sqlalchemy_engine()
    inspector = inspect(engine)
    schema = (
        resolve_schema("target", target.schema, list(inspector.get_schema_names()), inspector.dialect)
        if target.schema
        else None
    )
    crud = BulkCrud(engine, parallel=_parallel(options))
    try:
        table = crud.reflect_table(_qualified(schema, options.table))
    except Exception:
        manager.close()
        raise LookupError(f"La tabla «{options.table}» no existe en el destino.") from None
    columns = [c.name for c in table.columns]
    pk = [c.name for c in table.primary_key.columns]
    mapping = _resolve_mapping(list(frame.columns), columns, options.mapping)
    errors: list[str] = []
    if mapping["unknown"]:
        errors.append(f"Columnas que no existen en la tabla: {', '.join(mapping['unknown'])}.")
    if mapping["missing_in_file"]:
        errors.append(f"Columnas del mapeo que no están en el fichero: {', '.join(mapping['missing_in_file'])}.")
    if not mapping["resolved"]:
        errors.append("Ninguna columna del fichero corresponde a la tabla.")
    loaded = set(mapping["resolved"].values())
    if options.operation == "insert":
        absent = [c for c in _required_columns(table) if c not in loaded]
        if absent:
            errors.append(f"Faltan columnas obligatorias: {', '.join(absent)}.")
    else:
        if not pk:
            errors.append("La tabla no tiene clave primaria: no se puede actualizar ni borrar por fichero.")
        elif missing_pk := [c for c in pk if c not in loaded]:
            errors.append(f"Falta la clave primaria en el fichero: {', '.join(missing_pk)}.")
        if options.operation == "update" and not (loaded - set(pk)):
            errors.append("No hay columnas que actualizar además de la clave primaria.")
    mapped = frame[list(mapping["resolved"])].rename(columns=mapping["resolved"])
    if options.operation == "delete" and pk and not errors:
        mapped = mapped[pk]
    return {
        "frame": mapped, "crud": crud, "manager": manager, "engine": engine, "table": table, "pk": pk,
        "schema": schema, "mapping": mapping, "errors": errors, "rows": len(frame),
    }  # fmt: skip


def _keys(frame: Any, pk: list[str]) -> list[tuple[Any, ...]]:
    return [tuple(None if v != v else v for v in row) for row in frame[pk].itertuples(index=False)]


def structure_hash(prepared: dict[str, Any], options: BulkOptions) -> str:
    """Huella de lo que se cargará: operación, tabla, columnas y PK de la tabla y mapeo resuelto (no los datos)."""
    payload = json.dumps(
        [options.operation, prepared["schema"], options.table, [c.name for c in prepared["table"].columns],
         prepared["pk"], sorted(prepared["mapping"]["resolved"].items())]
    )  # fmt: skip
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_bulk_preview(
    target: Target, frame: Any, options: BulkOptions, *, outputs_dir: Path, work_dir: Path
) -> dict[str, Any]:
    """Modo seco: validaciones, muestra, filas afectadas, plan paralelo y SQL generado (sin tocar el destino).

    Raises:
        LookupError: La tabla no existe.
    """
    prepared = _prepare(target, frame, options)
    try:
        frame, crud, table, pk = prepared["frame"], prepared["crud"], prepared["table"], prepared["pk"]
        matches = None
        if pk and set(pk) <= set(frame.columns) and not prepared["errors"]:
            matches = _count_matches(prepared["engine"], table, _keys(frame, pk), pk)
        plan = crud.parallel_plan(options.operation, len(frame))
        sql_file: str | None = None
        if not prepared["errors"] and len(frame):
            table_name = _qualified(prepared["schema"], options.table)
            sql_file = _generate_sql(crud, frame, options, table_name, outputs_dir, work_dir)
        return {
            "table": options.table,
            "schema": prepared["schema"],
            "operation": options.operation,
            "rows": prepared["rows"],
            "columns": list(frame.columns),
            "mapping": prepared["mapping"]["resolved"],
            "ignored_columns": prepared["mapping"]["ignored"],
            "primary_key": pk,
            "errors": prepared["errors"],
            "matches": matches,
            "target_rows": _count(prepared["engine"], table),
            "parallel": {"workers": plan.workers, "reasons": list(plan.reasons), "atomic": plan.atomic},
            "sample": _frame_records(frame, SAMPLE_ROWS),
            "sql_file": sql_file,
            "structure_hash": structure_hash(prepared, options),
        }
    finally:
        prepared["manager"].close()


def _call(crud: Any, operation: Operation, frame: Any, table: str, **kwargs: Any) -> None:
    method = {"insert": crud.bulk_insert_from_df, "update": crud.bulk_update_from_df,
              "delete": crud.bulk_delete_from_df}[operation]  # fmt: skip
    method(frame, table, **kwargs)


def _generate_sql(
    crud: Any, frame: Any, options: BulkOptions, table_name: str, outputs_dir: Path, work_dir: Path
) -> str:
    """SQL de la operación sin ejecutarla (``dry_run=True``), en ``outputs/sql/carga_<op>.sql``."""
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        _call(crud, options.operation, frame, table_name, dry_run=True, path_sql=work_dir)
        produced = sorted(work_dir.glob("*.sql"))
        target = outputs_dir / "sql" / SQL_FILE.format(op=options.operation)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as out:
            for part in produced:
                out.write(part.read_bytes())
        return target.relative_to(outputs_dir).as_posix()
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def run_bulk(
    target: Target,
    frame: Any,
    options: BulkOptions,
    *,
    expected_structure: str,
    outputs_dir: Path,
    expected_matches: int | None = None,
    progress: RunProgress | None = None,
) -> dict[str, Any]:
    """Vuelve a validar, exige la misma estructura y ejecuta la operación (``dry_run=False``).

    Con ``progress`` emite el avance por lote y para entre lotes si se cancela su token (``cancelled`` en el resultado).

    Returns:
        Resultado: filas del fichero, filas confirmadas según util_bbdd, coincidencias por PK, filas del destino antes y
        después y su verificación, rechazadas, plan paralelo y particiones (con errores saneados).

    Raises:
        StructureChangedError: La tabla o el mapeo cambiaron. ``MatchesChangedError``: en update/delete, las filas
            afectadas ya no son ``expected_matches`` (las confirmadas). ``ValueError``: el fichero ya no valida.
    """
    from util_bbdd.audit import JsonLinesAuditSink
    from util_bbdd.bulk import AuditOptions, BatchOptions, BulkCrud, RejectOptions

    prepared = _prepare(target, frame, options)
    try:
        if structure_hash(prepared, options) != expected_structure:
            raise StructureChangedError()
        if prepared["errors"]:
            raise ValueError("; ".join(prepared["errors"]))
        frame, table, pk, engine = prepared["frame"], prepared["table"], prepared["pk"], prepared["engine"]
        matches = _count_matches(engine, table, _keys(frame, pk), pk) if pk else None
        if options.operation != "insert" and expected_matches is not None and matches != expected_matches:
            raise MatchesChangedError(f"{matches}")
        before = _count(engine, table)
        rejects = outputs_dir / "rejects" / REJECTS_FILE
        audit_path = outputs_dir / "audit" / AUDIT_FILE
        for folder in (rejects.parent, audit_path.parent):
            folder.mkdir(parents=True, exist_ok=True)
        sink = JsonLinesAuditSink(audit_path)
        crud = BulkCrud(
            engine,
            batch=BatchOptions(chunk_size=options.chunk_size),
            audit=AuditOptions(sink=sink, warn_if_disabled=False),
            rejects=RejectOptions(
                on_error=options.on_error,
                csv_path=rejects if options.on_error == "isolate" else None,
                max_rejects=options.max_rejects if options.on_error == "isolate" else None,
            ),
            parallel=_parallel(options),
        )
        plan = crud.parallel_plan(options.operation, len(frame))
        error: str | None = None
        cancelled = False
        try:
            _call(
                crud, options.operation, frame, _qualified(prepared["schema"], options.table), dry_run=False,
                on_progress=progress, cancel_token=progress.token if progress is not None else None,
            )  # fmt: skip
        except Exception as exc:  # fallo o cancelación: el resultado lo cuenta (filas antes/después)
            if is_cancellation(exc):
                cancelled = True
            else:
                error = _clean(str(exc.__cause__ or exc))
        finally:
            sink.close()
        after = _count(engine, table)
        parallel = crud.last_parallel_result
        partitions = [
            {"index": p.index, "rows": p.rows, "error": _clean(p.error) if p.error else None}
            for p in (parallel.partition_results if parallel else [])
        ]
        committed = crud.last_operation_rows_committed
        complete = (
            not cancelled and error is None and crud.rows_rejected == 0 and not any(p["error"] for p in partitions)
        )
        return {
            "operation": options.operation,
            "table": options.table,
            "rows": len(frame),
            "committed": committed,
            "matches": matches,
            "target_rows_before": before,
            "target_rows_after": after,
            "verified": verify(options.operation, before, after, committed, matches) if complete else None,
            "rejected": crud.rows_rejected,
            "error": error,
            "cancelled": cancelled,
            "parallel": {"workers": plan.workers, "reasons": list(plan.reasons), "atomic": plan.atomic},
            "partitions": partitions,
        }
    finally:
        prepared["manager"].close()


def verify(operation: Operation, before: int, after: int, committed: int, matches: int | None) -> bool | None:
    """Si el recuento del destino cuadra con lo que util_bbdd dice haber confirmado (G37: se mantiene como defensa).

    Solo tiene sentido en una carga completa (sin rechazos, error ni particiones fallidas): insert crece en
    ``committed``; delete decrece en ``matches`` (las filas distintas del destino con esas claves; ``committed`` cuenta
    también claves que no existen); update no cambia el número de filas. ``None``: no se puede comprobar.
    """
    if operation == "insert":
        return after - before == committed
    if operation == "delete":
        return None if matches is None else before - after == matches
    return after == before
