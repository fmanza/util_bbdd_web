"""Comparación de esquemas con util_bbdd (Fase 6); se ejecuta dentro del subproceso del job.

- ``SchemaComparator().compare(inspector_origen, inspector_destino, *, source_schema, target_schema, include_*)``
  devuelve un ``SchemaDiff``; se guarda con ``SchemaDiff.to_dict()`` y se relee con ``SchemaDiff.from_dict()``
  (util_bbdd 4.2.0, GAPS G24). ``read_diff`` sigue leyendo el formato 1 propio de la web (runs hasta la 1.1.0).
- Etiquetas: ``alias (motor) [schema]`` con ``source_label``/``target_label`` (util_bbdd 4.2.0, G23). Sin ellas
  util_bbdd ya no pone host, usuario ni ruta (``motor [schema]``), pero el alias es lo que reconoce el usuario.
- ``SchemaDiffReporter(sql_dialect, sql_source_inspector, sql_source_schema).render(diff, dir, formato, filename)``
  genera los informes con nombre fijo. El HTML se deja en ``outputs/html/comparacion/index.html`` para servirlo por la
  URL firmada del sitio (ADR-007). La CSP del sitio no admite orígenes externos: Mermaid (12.x) va incrustado con
  ``mermaid_src=Path`` (``UBW_MERMAID_JS``); sin el fichero, ``mermaid_src=None`` (util_bbdd 4.2.0, G25) y el informe
  funciona sin Mermaid (pestañas, filtros, búsqueda), con los diagramas como texto.
- Progreso y cancelación (util_bbdd 4.2.0, GAPS G1): ``RunProgress`` como ``on_progress`` y su token; la comparación
  para entre tablas (``OperationCancelledError``). Los informes, que van después, no se interrumpen.
- El script SQL **solo se genera**: transforma el destino para igualarlo al origen y no se ejecuta nunca aquí.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from app.integrations.util_bbdd.progress import RunProgress

#: Formato 1 propio de la web (hasta 1.1.0): ``dataclasses.asdict`` del ``SchemaDiff`` + ``format`` y contadores.
#: Desde 1.2.0 ``outputs/diff/schema_diff.json`` es ``SchemaDiff.to_dict()``; el formato 1 solo se lee.
LEGACY_DIFF_FORMAT: Final = 1
DIFF_FILE: Final = "schema_diff.json"
REPORT_FORMATS: Final = ("html", "excel", "word", "markdown", "sql")
_EXTENSIONS: Final[dict[str, str]] = {
    "html": ".html",
    "excel": ".xlsx",
    "word": ".docx",
    "markdown": ".md",
    "sql": ".sql",
}
#: Motor de la web → dialecto del ``SqlDiffReporter`` (HSQLDB no tiene dialecto propio).
_SQL_DIALECTS: Final[dict[str, str]] = {
    "mariadb": "mariadb",
    "mysql": "mysql",
    "postgresql": "postgresql",
    "sqlserver": "sqlserver",
    "oracle": "oracle",
    "sqlite": "sqlite",
}


@dataclass(frozen=True)
class Side:
    """Un lado de la comparación: motor, ``conn_params`` ya preparados, schema y etiqueta pública."""

    db_type: str
    conn_params: dict[str, Any]
    schema: str | None
    alias: str

    @property
    def label(self) -> str:
        suffix = f" [{self.schema}]" if self.schema else ""
        return f"{self.alias} ({self.db_type}){suffix}"


@dataclass(frozen=True)
class CompareOptions:
    """Qué se compara y qué informes se generan."""

    tables: bool = True
    views: bool = True
    indexes: bool = True
    foreign_keys: bool = True
    comments: bool = True
    routines: bool = False
    formats: tuple[str, ...] = REPORT_FORMATS
    sql_dialect: str = "auto"


def sql_dialect_for(option: str, target_db_type: str) -> str:
    """Dialecto del script SQL: el elegido o, con ``auto``, el del motor destino (``generic`` si no tiene)."""
    if option != "auto":
        return option
    return _SQL_DIALECTS.get(target_db_type, "generic")


class SchemaNotFoundError(LookupError):
    """El schema pedido no existe en un lado (``side`` = ``source``/``target``)."""

    def __init__(self, side: str, schema: str) -> None:
        super().__init__(f"El schema «{schema}» no existe en el {_SIDE_NAMES[side]}.")
        self.side = side


_SIDE_NAMES: Final = {"source": "origen", "target": "destino"}


def resolve_schema(side: str, schema: str | None, available: list[str], dialect: Any) -> str | None:
    """Nombre de schema tal como lo espera el ``Inspector``, comprobando que existe.

    ``available`` son los nombres de ``Inspector.get_schema_names()``. En Oracle SQLAlchemy los normaliza a
    minúsculas (``BENCH`` → ``bench``) y un nombre en minúsculas se toma como sensible a mayúsculas; por eso se compara
    con el nombre real del catálogo y, si no coincide exacto, se acepta una única coincidencia sin distinguir
    mayúsculas. Sin esta comprobación, un schema mal escrito da un diff vacío («Sin diferencias»).

    Raises:
        SchemaNotFoundError: No existe en ese lado.
    """
    if not schema:
        return None
    normalize = getattr(dialect, "requires_name_normalize", False)
    real = {(dialect.denormalize_name(n) if normalize else n): n for n in available}
    if schema in real:
        return real[schema]
    matches = [name for name in real if name.lower() == schema.lower()]
    if len(matches) != 1:
        raise SchemaNotFoundError(side, schema)
    return real[matches[0]]


def progress_phases(options: CompareOptions) -> tuple[str, ...]:
    """Fases de ``SchemaComparator.compare()`` que emiten eventos con estas opciones, en orden."""
    phases: tuple[str, ...] = ("metadata", "tables") if options.tables else ()
    return phases + (("views",) if options.views else ()) + (("routines",) if options.routines else ())


def diff_to_dict(diff: Any) -> dict[str, Any]:
    """JSON del diff que se guarda: el de util_bbdd (``format="util_bbdd.schema_diff"`` y ``format_version``)."""
    data: dict[str, Any] = diff.to_dict()
    return data


def read_diff(data: Mapping[str, Any]) -> dict[str, Any]:
    """Diff guardado → campos del ``SchemaDiff`` más ``has_differences``, ``total_differences`` y
    ``total_leaf_differences``, que es lo que leen el visor y la evolución.

    Acepta ``SchemaDiff.to_dict()`` de util_bbdd (runs desde la 1.2.0) y el formato 1 propio (runs anteriores), así la
    evolución funciona entre runs de las dos épocas.

    Raises:
        ValueError: Ni uno ni otro (fichero dañado o de una versión de util_bbdd que esta no lee).
    """
    if not isinstance(data, Mapping):
        raise ValueError(f"El diff guardado no es un objeto JSON: {type(data).__name__}")
    if data.get("format") == LEGACY_DIFF_FORMAT:
        return dict(data)
    from util_bbdd.comparar import SchemaDiff
    from util_bbdd.exceptions import SchemaDiffValidationError

    try:
        diff = SchemaDiff.from_dict(data)
    except SchemaDiffValidationError as exc:
        raise ValueError(str(exc)) from exc
    return {**diff_to_dict(diff), **_counters(diff)}


def _counters(diff: Any) -> dict[str, Any]:
    return {
        "has_differences": diff.has_differences,
        "total_differences": diff.total_differences,
        "total_leaf_differences": diff.total_leaf_differences,
    }


def compare_schemas(
    source: Side,
    target: Side,
    *,
    options: CompareOptions,
    outputs_dir: Path,
    on_phase: Any = None,
    progress: RunProgress | None = None,
    mermaid_js: Path | None = None,
) -> dict[str, Any]:
    """Compara, guarda ``outputs/diff/schema_diff.json`` y genera los informes pedidos.

    Args:
        on_phase: ``callable(fase, mensaje)`` opcional para el progreso.
        progress: Progreso por fase y tabla y cancelación cooperativa (fases ``progress_phases(options)``).
        mermaid_js: ``mermaid.min.js`` que se incrusta en el informe HTML; ``None``, sin Mermaid.

    Returns:
        ``{"summary", "has_differences", "total_differences", "total_leaf_differences", "reports": {formato: ruta}}``
        (rutas relativas a ``outputs_dir``).

    Raises:
        SideError: Fallo al conectar o leer un lado (``side`` = ``source``/``target``); el resto, de util_bbdd.
    """
    from sqlalchemy import inspect
    from util_bbdd import SyncDatabaseManager
    from util_bbdd.comparar import SchemaComparator, SchemaDiffReporter

    def phase(name: str, message: str) -> None:
        if on_phase is not None:
            on_phase(name, message)

    phase("connecting", f"Conectando con el origen «{source.alias}»")
    with SyncDatabaseManager(source.db_type, source.conn_params, use_pool=False) as source_manager:
        source_inspector = _inspect(inspect, source_manager, "source")
        phase("connecting", f"Conectando con el destino «{target.alias}»")
        with SyncDatabaseManager(target.db_type, target.conn_params, use_pool=False) as target_manager:
            target_inspector = _inspect(inspect, target_manager, "target")
            source_schema = _resolve(source_inspector, "source", source.schema)
            target_schema = _resolve(target_inspector, "target", target.schema)
            phase("running", "Comparando los esquemas")
            diff = SchemaComparator().compare(
                source_inspector,
                target_inspector,
                source_schema=source_schema,
                target_schema=target_schema,
                include_tables=options.tables,
                include_views=options.views,
                include_indices=options.indexes,
                include_foreign_keys=options.foreign_keys,
                include_comments=options.comments,
                include_routines=options.routines,
                source_label=source.label,
                target_label=target.label,
                on_progress=progress,
                cancel_token=progress.token if progress is not None else None,
            )
            data = diff_to_dict(diff)
            diff_dir = outputs_dir / "diff"
            diff_dir.mkdir(parents=True, exist_ok=True)
            (diff_dir / DIFF_FILE).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

            phase("reporting", "Generando los informes")
            reporter = SchemaDiffReporter(
                sql_dialect=sql_dialect_for(options.sql_dialect, target.db_type),
                sql_source_inspector=source_inspector,
                sql_source_schema=source_schema,
                mermaid_src=mermaid_js,  # incrustado o None: sin scripts de otros orígenes (CSP del sitio, ADR-007)
            )
            reports: dict[str, str] = {}
            for fmt in options.formats:
                folder, filename = _report_location(outputs_dir, fmt)
                path = reporter.render(diff, folder, fmt, filename=filename)
                reports[fmt] = path.relative_to(outputs_dir).as_posix()
    return {"summary": diff.summary, **_counters(diff), "reports": reports}


class SideError(RuntimeError):
    """Fallo al conectar o inspeccionar un lado; ``side`` es ``source`` o ``target``."""

    def __init__(self, side: str, cause: Exception) -> None:
        super().__init__(side)
        self.side = side
        self.cause = cause


def _inspect(inspect: Any, manager: Any, side: str) -> Any:
    try:
        return inspect(manager.get_sqlalchemy_engine())
    except Exception as exc:  # frontera de util_bbdd/SQLAlchemy: se clasifica fuera, sin el texto
        raise SideError(side, exc) from exc


def _resolve(inspector: Any, side: str, schema: str | None) -> str | None:
    if not schema:
        return None
    try:
        available = list(inspector.get_schema_names())
    except Exception as exc:  # frontera de SQLAlchemy
        raise SideError(side, exc) from exc
    return resolve_schema(side, schema, available, inspector.dialect)


def _report_location(outputs_dir: Path, fmt: str) -> tuple[Path, str]:
    if fmt == "html":
        return outputs_dir / "html" / "comparacion", "index.html"
    return outputs_dir / fmt, f"comparacion{_EXTENSIONS[fmt]}"
