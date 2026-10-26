"""Migración DDL con util_bbdd (Fase 7, ADR-008); se ejecuta dentro del subproceso del job.

- ``MigrationPlanner(source_engine, target_engine, **opciones).plan(manager_origen, schema) -> MigrationPlan``.
- ``MigrationPlan`` no se serializa ni se reconstruye (GAPS G26): para aplicar **exactamente** lo revisado se vuelve
  a planificar y se compara el hash SHA-256 de ``emit_statements()`` con el del plan guardado.
- ``MigrationPlan.execute`` aplica sentencia a sentencia con ``commit`` y **no es atómico** (G27): si una falla, las
  anteriores quedan. El modo seco (``dry_run``) comprueba conflictos con tablas existentes y valida vistas
  (``validate_views``: transacción deshecha en PostgreSQL/SQL Server, solo sintaxis en el resto) sin dejar cambios.
- util_bbdd puede emitir FK entre columnas de tipos distintos (Oracle ``INT``: PK → ``INT(11)``, FK → ``DOUBLE``; G28).
  La web las detecta (``fk_mismatches``): el visor avisa siempre y, con destino MariaDB/MySQL (que siempre las
  rechaza), el modo seco falla.
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
AUDIT_FILE: Final = "migracion.jsonl"


class PlanBlockedError(ValueError):
    """El plan tiene avisos de severidad ``ERROR``: util_bbdd no lo ejecuta."""


class FkTypeMismatchError(RuntimeError):
    """FK entre columnas de tipos distintos en un destino que las rechaza (MariaDB/MySQL)."""


class PlanChangedError(RuntimeError):
    """El origen ha cambiado desde el plan revisado (el hash de las sentencias no coincide)."""


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
    """FK del plan cuya columna y columna referenciada tienen tipos destino distintos (GAPS G28)."""
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
    """Planifica y guarda ``outputs/plan/plan.json`` y ``outputs/sql/migracion_<destino>.sql``.

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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _target_tables(manager: Any, plan: Any, schema: str | None) -> list[str]:
    """Tablas del plan cuyo nombre ya usa una tabla o vista del destino.

    ``schema``: donde crea las tablas el script (``pg_schema`` con destino PostgreSQL, que emite ``SET search_path``);
    ``None`` = el schema por defecto de la conexión.
    """
    from sqlalchemy import inspect

    inspector = inspect(manager.get_sqlalchemy_engine())
    names = [*inspector.get_table_names(schema=schema), *inspector.get_view_names(schema=schema)]
    existing = {name.lower() for name in names}
    return sorted(table.name for table in plan.tables if table.name.lower() in existing)


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
    source: tuple[str, dict[str, Any]],
    target: tuple[str, dict[str, Any]],
    *,
    schema: str,
    options: PlannerOptions,
    expected_hash: str,
    mode: Literal["dry_run", "apply"],
    outputs_dir: Path,
) -> ApplyReport:
    """Vuelve a planificar, comprueba el hash y, según ``mode``, valida (sin cambios) o aplica en el destino.

    Raises:
        PlanChangedError: El origen cambió desde el plan revisado.
        PlanBlockedError: El plan tiene avisos ``ERROR``.
        TargetConflictError: Solo en ``apply``: el destino ya tiene tablas del plan (en ``dry_run`` se informan).
        FkTypeMismatchError: Solo en ``apply`` con destino MariaDB/MySQL (en ``dry_run`` se informa).
    """
    from util_bbdd import SyncDatabaseManager
    from util_bbdd.audit import JsonLinesAuditSink

    source_type, source_params = source
    target_type, target_params = target
    with SyncDatabaseManager(source_type, source_params, use_pool=False) as source_manager:
        plan = _plan(source_type, target_type, source_manager, schema, options)
    statements = list(plan.emit_statements())
    current = statements_hash(statements)
    if current != expected_hash:
        raise PlanChangedError(current)
    if plan.error_count:
        raise PlanBlockedError(str(plan.error_count))
    checked = plan_to_dict(plan, statements)
    report = ApplyReport(
        mode=mode,
        statements_hash=current,
        statements=len(statements),
        fk_mismatches=checked["fk_mismatches"],
        fk_blocking=checked["fk_blocking"],
    )
    if mode == "apply" and report.fk_blocking:
        raise FkTypeMismatchError(str(len(report.fk_mismatches)))
    with SyncDatabaseManager(target_type, target_params, use_pool=False) as target_manager:
        target_schema = options.pg_schema if target_type == "postgresql" else None
        report.conflicts = _target_tables(target_manager, plan, target_schema)
        if mode == "dry_run":
            if plan.views:
                report.views = _view_results(plan.validate_views(target_manager, include_tables=True))
            return report
        if report.conflicts:
            raise TargetConflictError(report.conflicts)
        audit_path = outputs_dir / "audit" / AUDIT_FILE
        sink = JsonLinesAuditSink(audit_path)
        try:
            plan.execute(target_manager, audit_sink=sink)
        except Exception as exc:
            _record_failure(report, audit_path, exc)
        finally:
            sink.close()
    if report.error is None:
        report.applied = report.statements
    return report


def _record_failure(report: ApplyReport, audit_path: Path, exc: Exception) -> None:
    """Rellena el informe con la sentencia que falló (del rastro de auditoría) y el mensaje del motor recortado."""
    applied = 0
    for line in audit_path.read_text(encoding="utf-8").splitlines() if audit_path.exists() else []:
        event = json.loads(line)
        if event.get("kind") != "statement":
            continue
        attributes = dict(event.get("attributes") or {})
        if event.get("status") == "ok":
            applied += 1
        else:
            report.failed_position = attributes.get("position")
            report.failed_statement = str(event.get("message") or "")[:200] or None
    report.applied = applied
    report.error = _engine_message(exc.__cause__ or exc)
