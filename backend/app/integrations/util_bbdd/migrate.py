"""Migración DDL con util_bbdd (Fase 7, ADR-008); se ejecuta dentro del subproceso del job.

- ``MigrationPlanner(source_engine, target_engine, **opciones).plan(manager_origen, schema) -> MigrationPlan``.
- El plan se guarda dos veces: ``plan.json`` (formato propio del visor, con ``statements_hash``) y
  ``migration_plan.json`` (``MigrationPlan.to_dict()``, util_bbdd 4.3.0, GAPS G26). Al aplicar, ``restore_plan``
  reconstruye el plan revisado con ``from_dict()`` y exige que ``statements_sha256()`` sea el ``statements_hash`` del
  visor: se ejecuta exactamente lo revisado sin volver a leer el origen. Los planes anteriores a la 1.3.0 (sin
  ``migration_plan.json``) se replanifican y se comparan igual (``replan``); los dos hashes usan el mismo algoritmo.
- ``MigrationPlan.execute`` aplica sentencia a sentencia con ``commit`` y **no es atómico** (G27): si una falla, las
  anteriores quedan y ``MigrationStatementError`` dice cuál. El modo seco comprueba el destino con ``check_target``
  (tablas y vistas que ya existen; vistas validadas: transacción deshecha en PostgreSQL/SQL Server, solo sintaxis en
  el resto) y cuenta las sentencias con ``execute(dry_run=True)``, sin conectar para escribir.
- Progreso por sentencia y cancelación **solo entre sentencias** (util_bbdd 4.3.0, G1): ``RunProgress`` como
  ``on_progress`` y su token. Al cancelar, las sentencias ya aplicadas quedan (el DDL no se deshace) y el informe dice
  cuántas (``cancelled``).
- Desde util_bbdd 4.3.0 la FK recibe el tipo destino de la columna referenciada (aviso ``FK_TYPE_ALIGNED``) o el plan
  queda bloqueado (``FK_TYPE_UNRESOLVED``, ``ERROR``; G28). ``fk_mismatches`` se mantiene como defensa para los planes
  guardados antes (Oracle ``INT``: PK → ``INT(11)``, FK → ``DOUBLE``) y ante regresiones: el visor avisa y, con
  destino MariaDB/MySQL (que siempre las rechaza), el modo seco falla.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

from app.integrations.util_bbdd.sql import _engine_message

PLAN_FORMAT: Final = 1
#: Destinos que rechazan siempre una FK entre tipos distintos (InnoDB).
FK_STRICT_TARGETS: Final = frozenset({"mariadb", "mysql"})
_INT_WIDTH = re.compile(r"^(TINYINT|SMALLINT|MEDIUMINT|INT|INTEGER|BIGINT)\(\d+\)")
PLAN_FILE: Final = "plan.json"
#: ``MigrationPlan.to_dict()`` de util_bbdd (desde la 1.3.0); los planes anteriores no lo tienen.
UTIL_BBDD_PLAN_FILE: Final = "migration_plan.json"
AUDIT_FILE: Final = "migracion.jsonl"


class PlanBlockedError(ValueError):
    """El plan tiene avisos de severidad ``ERROR``: util_bbdd no lo ejecuta."""


class FkTypeMismatchError(RuntimeError):
    """FK entre columnas de tipos distintos en un destino que las rechaza (MariaDB/MySQL)."""


class PlanChangedError(RuntimeError):
    """El plan a aplicar no emite las sentencias revisadas (el hash no coincide): el origen cambió desde el plan."""


class PlanOutdatedError(RuntimeError):
    """``migration_plan.json`` no se puede reconstruir: otra versión de util_bbdd emite otro DDL, o está dañado."""


class TargetConflictError(RuntimeError):
    """El destino ya tiene tablas que el plan crearía."""

    def __init__(self, tables: list[str]) -> None:
        super().__init__(", ".join(tables))
        self.tables = tables


@dataclass(frozen=True)
class PlannerOptions:
    """Opciones de ``MigrationPlanner`` que expone el formulario (las de MariaDB/MySQL solo aplican a ese destino)."""

    charset: str | None = None
    collation: str | None = None
    number_fallback: Literal["DOUBLE", "DECIMAL(38,10)", "DECIMAL(18,4)"] = "DOUBLE"
    storage_engine: str = "InnoDB"
    int_display_width: int = 11
    sql_server_collation: str | None = None
    pg_schema: str | None = None
    oracle_identity_mode: Literal["sequence_trigger", "identity"] = "sequence_trigger"
    view_strategy: Literal["auto", "transpile", "passthrough"] = "auto"

    def kwargs(self) -> dict[str, Any]:
        """Argumentos de ``MigrationPlanner`` (sin los ``None``: util_bbdd pone sus valores por defecto)."""
        values: dict[str, Any] = {
            "charset": self.charset,
            "collation": self.collation,
            "number_fallback": self.number_fallback,
            "engine": self.storage_engine,
            "int_display_width": self.int_display_width,
            "sql_server_collation": self.sql_server_collation,
            "pg_schema": self.pg_schema,
            "oracle_identity_mode": self.oracle_identity_mode,
            "view_strategy": self.view_strategy,
        }
        return {key: value for key, value in values.items() if value is not None}


def statements_hash(statements: list[str]) -> str:
    """SHA-256 de las sentencias del plan (separadas por un NUL, que no aparece en SQL)."""
    return hashlib.sha256("\x00".join(statements).encode("utf-8")).hexdigest()


def _warning(warning: Any) -> dict[str, Any]:
    data = asdict(warning)
    data["proposals"] = list(data.get("proposals") or ())
    return data


def _normalized_type(target_type: str) -> str:
    """Tipo comparable: sin espacios de más, en mayúsculas y sin el ancho de visualización de los enteros."""
    compact = re.sub(r"\s+", " ", target_type.strip().upper())
    return _INT_WIDTH.sub(r"\1", compact)


def fk_mismatches(tables: list[dict[str, Any]]) -> list[dict[str, str]]:
    """FK del plan cuya columna y columna referenciada tienen tipos destino distintos (GAPS G28).

    Con util_bbdd 4.3.0 debería devolver siempre una lista vacía; se mantiene como defensa (planes anteriores).
    """
    types = {
        (table["name"].lower(), col["name"].lower()): col["target_type"] for table in tables for col in table["columns"]
    }
    result: list[dict[str, str]] = []
    for table in tables:
        for fk in table["foreign_keys"]:
            for column, ref_column in zip(fk["columns"], fk.get("ref_columns") or [], strict=False):
                own = types.get((table["name"].lower(), column.lower()))
                ref = types.get((fk["ref_table"].lower(), ref_column.lower()))
                if own and ref and _normalized_type(own) != _normalized_type(ref):
                    result.append(
                        {
                            "table": table["name"],
                            "foreign_key": fk["name"],
                            "column": column,
                            "column_type": own,
                            "ref_table": fk["ref_table"],
                            "ref_column": ref_column,
                            "ref_type": ref,
                        }
                    )
    return result


def plan_to_dict(plan: Any, statements: list[str]) -> dict[str, Any]:
    """JSON del plan para el visor y para comprobarlo al aplicar (``statements_hash``)."""
    data: dict[str, Any] = {
        "format": PLAN_FORMAT,
        "source_engine": plan.source_engine,
        "target_engine": plan.target_engine,
        "source_schema": plan.source_schema,
        "error_count": plan.error_count,
        "warning_count": plan.warning_count,
        "info_count": plan.info_count,
        "statements_hash": statements_hash(statements),
        "statements": statements,
        "warnings": [_warning(w) for w in plan.warnings],
        "tables": [
            {
                "name": table.name,
                "original_name": table.original_name,
                "comment": table.comment,
                "primary_key": list(table.primary_key),
                "columns": [
                    {
                        "name": col.name,
                        "original_name": col.original_name,
                        "source_type": col.source_type,
                        "target_type": col.target_type,
                        "nullable": col.nullable,
                        "default": col.default,
                        "auto_increment": col.auto_increment,
                        "omit": col.omit,
                    }
                    for col in table.columns
                ],
                "indexes": [{"name": i.name, "columns": list(i.columns), "unique": i.unique} for i in table.indexes],
                "foreign_keys": [
                    {
                        "name": fk.name,
                        "columns": list(fk.columns),
                        "ref_table": fk.ref_table,
                        "ref_columns": list(fk.ref_columns),
                    }
                    for fk in table.foreign_keys
                ],
            }
            for table in plan.tables
        ],
        "views": [{"name": v.name, "original_name": v.original_name} for v in plan.views],
        "routines": [{"name": r.name, "routine_type": r.routine_type} for r in plan.routines],
    }
    data["fk_mismatches"] = fk_mismatches(data["tables"])
    data["fk_blocking"] = bool(data["fk_mismatches"]) and plan.target_engine in FK_STRICT_TARGETS
    return data


def _plan(source_engine: str, target_engine: str, manager: Any, schema: str, options: PlannerOptions) -> Any:
    from util_bbdd.migrate import MigrationPlanner

    planner = MigrationPlanner(source_engine=source_engine, target_engine=target_engine, **options.kwargs())
    return planner.plan(manager, schema)


def default_schema(db_type: str, conn_params: dict[str, Any], manager: Any) -> str:
    """Schema origen por defecto: el de la conexión (Oracle: el usuario; MySQL/MariaDB: la base de datos)."""
    from sqlalchemy import inspect

    if db_type == "oracle":
        return str(conn_params.get("user", "")).upper()
    if db_type in {"mysql", "mariadb"} and conn_params.get("database"):
        return str(conn_params["database"])
    return str(inspect(manager.get_sqlalchemy_engine()).default_schema_name or "")


def create_plan(
    db_type: str,
    conn_params: dict[str, Any],
    *,
    schema: str | None,
    target_engine: str,
    options: PlannerOptions,
    outputs_dir: Path,
) -> dict[str, Any]:
    """Planifica y guarda ``outputs/plan/plan.json``, ``outputs/plan/migration_plan.json`` y el script SQL.

    Returns:
        Resumen: tablas, vistas, rutinas, avisos por severidad, hash y rutas de los ficheros.
    """
    from util_bbdd import SyncDatabaseManager

    with SyncDatabaseManager(db_type, conn_params, use_pool=False) as manager:
        source_schema = schema or default_schema(db_type, conn_params, manager)
        plan = _plan(db_type, target_engine, manager, source_schema, options)
        statements = list(plan.emit_statements())
        ddl = plan.emit_ddl()
    data = plan_to_dict(plan, statements)
    (outputs_dir / "plan").mkdir(parents=True, exist_ok=True)
    (outputs_dir / "plan" / PLAN_FILE).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    (outputs_dir / "plan" / UTIL_BBDD_PLAN_FILE).write_text(json.dumps(plan.to_dict(), ensure_ascii=False), "utf-8")
    sql_path = outputs_dir / "sql" / f"migracion_{target_engine}.sql"
    sql_path.parent.mkdir(parents=True, exist_ok=True)
    sql_path.write_text(ddl, encoding="utf-8")
    return {
        "tables": len(data["tables"]),
        "views": len(data["views"]),
        "routines": len(data["routines"]),
        "statements": len(statements),
        "errors": data["error_count"],
        "warnings": data["warning_count"],
        "statements_hash": data["statements_hash"],
    }


@dataclass
class ApplyReport:
    """Resultado del modo seco o de la aplicación (``report.json`` del run)."""

    mode: Literal["dry_run", "apply"]
    statements_hash: str
    statements: int
    conflicts: list[str] = field(default_factory=list)
    views: list[dict[str, Any]] = field(default_factory=list)
    fk_mismatches: list[dict[str, str]] = field(default_factory=list)
    fk_blocking: bool = False
    applied: int = 0
    failed_position: int | None = None
    failed_statement: str | None = None
    error: str | None = None
    #: Se canceló entre dos sentencias: ``applied`` quedaron aplicadas.
    cancelled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def restore_plan(data: Any, expected_hash: str) -> Any:
    """``MigrationPlan`` revisado, reconstruido desde ``migration_plan.json`` (sin leer el origen).

    Raises:
        PlanOutdatedError: util_bbdd no lo acepta (otra versión emite otro DDL, o el fichero está dañado).
        PlanChangedError: No emite las sentencias del ``plan.json`` revisado.
    """
    from util_bbdd.exceptions import MigrationPlanValidationError
    from util_bbdd.migrate import MigrationPlan

    try:
        plan = MigrationPlan.from_dict(data)
    except MigrationPlanValidationError:
        raise PlanOutdatedError() from None
    current = plan.statements_sha256()
    if current != expected_hash:
        raise PlanChangedError(current)
    return plan


def replan(
    source: tuple[str, dict[str, Any]],
    target_engine: str,
    *,
    schema: str,
    options: PlannerOptions,
    expected_hash: str,
) -> Any:
    """Vuelve a planificar un plan anterior a la 1.3.0 (sin ``migration_plan.json``) y comprueba el hash.

    Raises:
        PlanChangedError: El origen cambió desde el plan revisado.
    """
    from util_bbdd import SyncDatabaseManager

    source_type, source_params = source
    with SyncDatabaseManager(source_type, source_params, use_pool=False) as source_manager:
        plan = _plan(source_type, target_engine, source_manager, schema, options)
    current = statements_hash(list(plan.emit_statements()))
    if current != expected_hash:
        raise PlanChangedError(current)
    return plan


def _check_target(plan: Any, manager: Any, *, validate_views: bool) -> tuple[list[str], list[dict[str, Any]]]:
    """Tablas y vistas del plan que ya existen en el destino y, si se pide, la validación de las vistas.

    ``check_target`` busca en el ``pg_schema`` del plan con destino PostgreSQL (el script emite ``SET search_path``) y,
    en el resto, en el schema por defecto de la conexión.
    """
    check = plan.check_target(manager, validate_views=validate_views)
    return sorted({conflict.name for conflict in check.conflicts}), _view_results(list(check.views))


def _view_results(results: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "view": getattr(r, "view", ""),
            "valid": getattr(r, "valid", None),
            "method": getattr(r, "method", ""),
            "error": _engine_message(RuntimeError(str(r.error))) if getattr(r, "error", None) else None,
        }
        for r in results
    ]


def apply_plan(
    plan: Any,
    target: tuple[str, dict[str, Any]],
    *,
    mode: Literal["dry_run", "apply"],
    outputs_dir: Path,
    progress: Any | None = None,
) -> ApplyReport:
    """Según ``mode``, comprueba el destino sin cambios (modo seco) o aplica el plan ya verificado.

    ``plan`` sale de ``restore_plan`` o ``replan`` (hash ya comprobado). ``progress`` (``RunProgress``, solo al aplicar)
    recibe un evento por sentencia; si se cancela su token, la aplicación para antes de la siguiente sentencia y el
    informe vuelve con ``cancelled`` y las aplicadas.

    Raises:
        PlanBlockedError: El plan tiene avisos ``ERROR``.
        TargetConflictError: Solo en ``apply``: el destino ya tiene tablas o vistas del plan (en ``dry_run`` se
            informan).
        FkTypeMismatchError: Solo en ``apply`` con destino MariaDB/MySQL (en ``dry_run`` se informa).
    """
    from util_bbdd import SyncDatabaseManager
    from util_bbdd.audit import JsonLinesAuditSink
    from util_bbdd.exceptions import MigrationStatementError, OperationCancelledError

    if plan.error_count:
        raise PlanBlockedError(str(plan.error_count))
    statements = list(plan.emit_statements())
    checked = plan_to_dict(plan, statements)
    report = ApplyReport(
        mode=mode,
        statements_hash=checked["statements_hash"],
        statements=plan.execute(None, dry_run=True).total,  # las que se envían (sin las de solo comentarios)
        fk_mismatches=checked["fk_mismatches"],
        fk_blocking=checked["fk_blocking"],
    )
    if mode == "apply" and report.fk_blocking:
        raise FkTypeMismatchError(str(len(report.fk_mismatches)))
    target_type, target_params = target
    with SyncDatabaseManager(target_type, target_params, use_pool=False) as target_manager:
        report.conflicts, report.views = _check_target(
            plan, target_manager, validate_views=mode == "dry_run" and bool(plan.views)
        )
        if mode == "dry_run":
            return report
        if report.conflicts:
            raise TargetConflictError(report.conflicts)
        sink = JsonLinesAuditSink(outputs_dir / "audit" / AUDIT_FILE)
        sent = _SentStatements(progress)
        try:
            result = plan.execute(
                target_manager,
                audit_sink=sink,
                on_progress=sent,
                cancel_token=progress.token if progress is not None else None,
            )
        except MigrationStatementError as exc:
            _record_failure(report, exc)
        except OperationCancelledError:
            report.cancelled = True
            report.applied = sent.count  # con stop_on_error, todas las enviadas se aplicaron
        else:
            report.applied = result.applied
        finally:
            sink.close()
    return report


class _SentStatements:
    """``on_progress`` que cuenta las sentencias enviadas (``current`` de la fase ``statements``) y reenvía el evento."""

    def __init__(self, progress: Any | None) -> None:
        self.count = 0
        self._progress = progress

    def __call__(self, event: Any) -> None:
        if event.phase == "statements":
            self.count = max(self.count, event.current)
        if self._progress is not None:
            self._progress(event)


def _record_failure(report: ApplyReport, exc: Any) -> None:
    """Rellena el informe con la sentencia que falló (``MigrationStatementError``) y el mensaje del motor recortado."""
    report.applied = exc.result.applied if exc.result is not None else max(exc.position - 1, 0)
    report.failed_position = exc.position
    report.failed_statement = exc.statement.strip().splitlines()[0][:200] if exc.statement.strip() else None
    report.error = _engine_message(exc.__cause__ or exc)
