"""SQL de solo lectura (Fase 4): guardián con ``sqlglot``, ejecución acotada y queries nombradas de util_bbdd.

Defensa en capas (el dominio comprueba además el permiso del usuario y que la conexión sea ``read_only``):

1. :func:`check_read_only`: una única sentencia ``SELECT``/``UNION``/``WITH … SELECT`` sin DML, DDL, ``INTO``,
   bloqueos ni comandos en ningún nodo (también dentro de CTE).
2. Transacción de solo lectura en el motor con ``execute_custom_result(read_only=True)`` de util_bbdd 5.0.0 (GAPS G19,
   G42): PostgreSQL, MySQL/MariaDB, Oracle y SQLite (``query_only``); en SQL Server, una transacción que se deshace.
3. ``max_rows=limit + 1`` (G20), timeout del subproceso y, en PostgreSQL, ``statement_timeout`` en el servidor.

``execute_custom_result`` usa la conexión del driver, no SQLAlchemy: en Oracle, oracledb devolvería ``NUMBER`` como
``float`` y perdería precisión (G44), así que la tarea pide ``Decimal`` (``fetch_decimals``, el ajuste es del
subproceso) y los enteros vuelven a ser ``int``. Los nombres de columna son los del driver (en Oracle, en mayúsculas).
util_bbdd 4.6.0 valida además todos los parámetros interpolados de las queries nombradas (G18), con la misma regla que
``PARAM_VALUE``, que se mantiene.
"""

from __future__ import annotations

import datetime as dt
import decimal
import json
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Final

from app.integrations.util_bbdd.isolated import PublicError, TaskResult, run_isolated

#: Dialecto de ``sqlglot`` por motor; HSQLDB no tiene y no admite SQL libre.
DIALECTS: Final[dict[str, str]] = {
    "postgresql": "postgres",
    "mysql": "mysql",
    "mariadb": "mysql",
    "oracle": "oracle",
    "sqlserver": "tsql",
    "sqlite": "sqlite",
}
#: Motores sin transacción de solo lectura: la UI avisa de que dependen del guardián.
WITHOUT_READ_ONLY_TRANSACTION: Final = frozenset({"sqlserver"})

_FORBIDDEN_NODES: Final = (
    "Insert", "Update", "Delete", "Merge", "Create", "Drop", "Alter", "Command", "Into", "Lock", "Copy", "Execute",
    "Pragma", "Set", "Transaction", "Commit", "Rollback", "Grant", "Revoke", "TruncateTable", "Use", "LoadData",
    "Refresh", "Cache", "Uncache", "Analyze", "Kill",
)  # fmt: skip
_ALLOWED_ROOTS: Final = ("Select", "Union", "Intersect", "Except", "Subquery")
MAX_CELL_CHARS: Final = 2000
MAX_ENGINE_MESSAGE: Final = 300
#: Valores admitidos en los parámetros de una query nombrada (``str.format`` de util_bbdd los interpola en crudo,
#: GAPS G18): identificadores o números.
PARAM_VALUE: Final = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_$#]{0,127}|-?\d{1,18}(?:\.\d{1,18})?)$")


class ReadOnlyViolation(ValueError):
    """El SQL no es una única sentencia de lectura."""


def check_read_only(sql: str, db_type: str) -> None:
    """Valida que ``sql`` sea una única sentencia de lectura.

    Raises:
        ReadOnlyViolation: Con un motivo para el usuario.
    """
    import sqlglot
    from sqlglot import expressions as exp
    from sqlglot.errors import ParseError

    dialect = DIALECTS.get(db_type)
    if dialect is None:
        raise ReadOnlyViolation(f"El SQL libre no está disponible para {db_type}.")
    try:
        statements = [s for s in sqlglot.parse(sql, read=dialect) if s is not None]
    except ParseError:
        raise ReadOnlyViolation("No se ha podido analizar el SQL; revisa la sintaxis.") from None
    if len(statements) != 1:
        raise ReadOnlyViolation("Escribe una única sentencia (sin «;» entre varias).")
    root = statements[0]
    if not isinstance(root, tuple(getattr(exp, n) for n in _ALLOWED_ROOTS)):
        raise ReadOnlyViolation("Solo se admiten consultas SELECT (también con WITH o UNION).")
    forbidden = tuple(getattr(exp, n) for n in _FORBIDDEN_NODES if hasattr(exp, n))
    for node in root.walk():
        if isinstance(node, forbidden):
            raise ReadOnlyViolation(f"La consulta contiene una operación no permitida ({type(node).__name__}).")


def template_params(sql_template: str) -> list[str]:
    """Nombres ``{param}`` de una plantilla de util_bbdd (en orden y sin repetir).

    Raises:
        ValueError: Plantilla mal formada (llaves sin cerrar, índices posicionales o atributos).
    """
    from string import Formatter

    names: list[str] = []
    for _, field, _, _ in Formatter().parse(sql_template):
        if field is None:
            continue
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", field):
            raise ValueError(f"Parámetro no válido en la plantilla: «{{{field}}}»")
        if field not in names:
            names.append(field)
    return names


def check_template(sql_template: str, db_type: str) -> list[str]:
    """Valida una plantilla de query nombrada: parámetros bien formados y SQL de solo lectura con valores de prueba.

    Returns:
        Nombres de los parámetros.

    Raises:
        ValueError, ReadOnlyViolation.
    """
    names = template_params(sql_template)
    check_read_only(sql_template.format(**dict.fromkeys(names, "x")), db_type)
    return names


# --- serialización -----------------------------------------------------------------------------------------------


def to_cell(value: Any) -> str | int | float | bool | None:
    """Valor de una celda a tipos JSON, con el texto truncado a ``MAX_CELL_CHARS``."""
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        return value if value == value and value not in (float("inf"), float("-inf")) else str(value)
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, dt.datetime | dt.date | dt.time):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, bytes | bytearray | memoryview):
        raw = bytes(value)
        text = "0x" + raw[: MAX_CELL_CHARS // 2].hex()
        return text + ("…" if len(raw) > MAX_CELL_CHARS // 2 else "")
    text = (
        value
        if isinstance(value, str)
        else (json.dumps(value, default=str) if isinstance(value, dict | list) else str(value))
    )
    return text if len(text) <= MAX_CELL_CHARS else text[:MAX_CELL_CHARS] + "…"


def _engine_message(exc: BaseException) -> str:
    """Primera línea del mensaje del motor, sin URL ni parámetros de SQLAlchemy, recortada."""
    original = getattr(exc, "orig", None) or exc
    text = str(original).strip().splitlines()[0] if str(original).strip() else type(original).__name__
    text = re.sub(r"\b[a-z][a-z0-9+]*://\S+", "[url]", text)  # nunca una URL de conexión
    text = text.split("[SQL:")[0].split("(Background on this error")[0].strip()
    return text[:MAX_ENGINE_MESSAGE]


# --- ejecución de solo lectura (en el subproceso) ----------------------------------------------------------------


def _oracle_number(value: Any) -> Any:
    """Con ``fetch_decimals`` todo ``NUMBER`` llega como ``Decimal``: los enteros vuelven a ``int``, como con SQLAlchemy."""
    if isinstance(value, decimal.Decimal):
        exponent = value.as_tuple().exponent
        if isinstance(exponent, int) and exponent >= 0:  # no 'n'/'N'/'F' (NaN, infinito)
            return int(value)
    return value


def _prepare_driver(db_type: str) -> None:
    """Ajustes del driver para el subproceso de la tarea (G44: ``NUMBER`` de Oracle sin pasar por ``float``)."""
    if db_type == "oracle":
        import oracledb

        oracledb.defaults.fetch_decimals = True


def _run_read_only(manager: Any, db_type: str, sql: str, limit: int, timeout: float) -> dict[str, Any]:
    from util_bbdd.exceptions import DatabaseOperationError

    start = time.monotonic()
    try:
        result = manager.execute_custom_result(sql, timeout=timeout, read_only=True, max_rows=limit + 1)
    except DatabaseOperationError as exc:
        raise PublicError("query_error", _engine_message(exc.__cause__ or exc)) from None
    convert = _oracle_number if db_type == "oracle" else None
    rows = [[to_cell(convert(v) if convert else v) for v in row] for row in result.rows[:limit]]
    return {
        "columns": [str(c) for c in result.columns],
        "rows": rows,
        "truncated": len(result.rows) > limit,
        "row_count": len(rows),
        "duration_ms": int((time.monotonic() - start) * 1000),
    }


def free_sql_task(db_type: str, conn_params: dict[str, Any], sql: str, limit: int, timeout: float) -> dict[str, Any]:
    """Tarea del subproceso: guardián + ejecución de solo lectura."""
    from util_bbdd import SyncDatabaseManager

    try:
        check_read_only(sql, db_type)
    except ReadOnlyViolation as exc:
        raise PublicError("not_read_only", str(exc)) from None
    _prepare_driver(db_type)
    with SyncDatabaseManager(db_type, conn_params, use_pool=False) as manager:
        return _run_read_only(manager, db_type, sql, limit, timeout)


def named_query_task(
    db_type: str,
    conn_params: dict[str, Any],
    name: str,
    sql_template: str,
    params: dict[str, str],
    limit: int,
    timeout: float,
) -> dict[str, Any]:
    """Tarea del subproceso: resuelve con util_bbdd (``queries_file`` temporal + ``resolve_query``), pasa el guardián
    sobre el SQL final y lo ejecuta en solo lectura."""
    from util_bbdd import SyncDatabaseManager
    from util_bbdd import exceptions as e

    _prepare_driver(db_type)
    with tempfile.TemporaryDirectory(prefix="ubw-queries-") as tmp:
        queries_file = Path(tmp) / "queries.json"
        queries_file.write_text(json.dumps({db_type: {name: sql_template}}), encoding="utf-8")
        with SyncDatabaseManager(db_type, conn_params, queries_file=queries_file, use_pool=False) as manager:
            try:
                final_sql = str(manager.resolve_query(name, **params).final_sql)
            except (e.QueryValidationError, e.QueryParameterError, e.QueryNotFoundError) as exc:
                raise PublicError(
                    "invalid_config", f"Parámetros no válidos para la query ({type(exc).__name__})."
                ) from None
            try:
                check_read_only(final_sql, db_type)
            except ReadOnlyViolation as exc:
                raise PublicError("not_read_only", str(exc)) from None
            return _run_read_only(manager, db_type, final_sql, limit, timeout)


# --- API para el dominio -----------------------------------------------------------------------------------------


def run_free_sql(db_type: str, conn_params: dict[str, Any], sql: str, *, limit: int, timeout: float) -> TaskResult:
    return run_isolated(
        f"{__name__}:free_sql_task",
        {"db_type": db_type, "conn_params": conn_params, "sql": sql, "limit": limit, "timeout": timeout},
        timeout=timeout + 5,
    )


def run_named_query(
    db_type: str,
    conn_params: dict[str, Any],
    *,
    name: str,
    sql_template: str,
    params: dict[str, str],
    limit: int,
    timeout: float,
) -> TaskResult:
    return run_isolated(
        f"{__name__}:named_query_task",
        {
            "db_type": db_type, "conn_params": conn_params, "name": name, "sql_template": sql_template,
            "params": params, "limit": limit, "timeout": timeout,
        },
        timeout=timeout + 5,
    )  # fmt: skip
