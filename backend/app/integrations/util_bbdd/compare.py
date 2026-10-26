"""Comparación de esquemas con util_bbdd (Fase 6); se ejecuta dentro del subproceso del job.

- ``SchemaComparator().compare(inspector_origen, inspector_destino, *, source_schema, target_schema, include_*)``
  devuelve un ``SchemaDiff`` (dataclasses inmutables, sin serialización propia: GAPS G24).
- Etiquetas: ``alias (motor) [schema]`` con ``source_label``/``target_label`` (util_bbdd 4.2.0, G23). Sin ellas
  util_bbdd ya no pone host, usuario ni ruta (``motor [schema]``), pero el alias es lo que reconoce el usuario.
- ``SchemaDiffReporter(sql_dialect, sql_source_inspector, sql_source_schema).render(diff, dir, formato, filename)``
  genera los informes con nombre fijo. El HTML se deja en ``outputs/html/comparacion/index.html`` para servirlo por la
  URL firmada del sitio (ADR-007). Ese HTML carga Mermaid de un CDN que la CSP bloquea, y sin ``mermaid`` aborta todo su
  script (pestañas, filtros, búsqueda): se cambia esa etiqueta por un sustituto local vacío (G25); los diagramas se
  ven como texto.
- El script SQL **solo se genera**: transforma el destino para igualarlo al origen y no se ejecuta nunca aquí.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

logger = logging.getLogger(__name__)

#: ``<script src>`` de Mermaid en un CDN dentro del informe HTML de util_bbdd (G25).
#: Desde util_bbdd 4.2.0 la etiqueta lleva ``integrity`` y ``crossorigin`` (versión fija con SRI).
_MERMAID_CDN = re.compile(r'<script\s+src="https://[^"]*mermaid[^"]*"[^>]*>\s*</script>', re.IGNORECASE)
MERMAID_STUB_PATH: Final = "assets/mermaid-stub.js"
MERMAID_STUB: Final = (
    "// Sustituto local de Mermaid (util_bbdd_web, GAPS G25): el informe lo carga de un CDN que la CSP del sitio\n"
    "// bloquea, y sin `mermaid` su script no arranca. Los diagramas se quedan como texto.\n"
    "window.mermaid = { initialize: function () {}, init: function () {}, "
    "run: function () { return Promise.resolve(); } };\n"
)

#: Versión del JSON del diff que guarda la web (``outputs/diff/schema_diff.json``).
DIFF_FORMAT: Final = 1
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


def diff_to_dict(diff: Any) -> dict[str, Any]:
    """JSON del diff: los campos del ``SchemaDiff`` más los contadores derivados y la versión del formato."""
    data: dict[str, Any] = dataclasses.asdict(diff)
    data.update(
        format=DIFF_FORMAT,
        has_differences=diff.has_differences,
        total_differences=diff.total_differences,
        total_leaf_differences=diff.total_leaf_differences,
    )
    return data


def compare_schemas(
    source: Side, target: Side, *, options: CompareOptions, outputs_dir: Path, on_phase: Any = None
) -> dict[str, Any]:
    """Compara, guarda ``outputs/diff/schema_diff.json`` y genera los informes pedidos.

    Args:
        on_phase: ``callable(fase, mensaje)`` opcional para el progreso.

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
            )
            reports: dict[str, str] = {}
            for fmt in options.formats:
                folder, filename = _report_location(outputs_dir, fmt)
                path = reporter.render(diff, folder, fmt, filename=filename)
                if fmt == "html":
                    localize_mermaid(path)
                reports[fmt] = path.relative_to(outputs_dir).as_posix()
    return {
        "summary": data["summary"],
        "has_differences": data["has_differences"],
        "total_differences": data["total_differences"],
        "total_leaf_differences": data["total_leaf_differences"],
        "reports": reports,
    }


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


def localize_mermaid(html_file: Path) -> bool:
    """Cambia el ``<script>`` de Mermaid del CDN por ``assets/mermaid-stub.js`` y escribe el sustituto.

    Returns:
        ``True`` si había etiqueta que cambiar (si util_bbdd deja de usarla, el informe queda como está).
    """
    html = html_file.read_text(encoding="utf-8")
    replaced, count = _MERMAID_CDN.subn(f'<script src="{MERMAID_STUB_PATH}"></script>', html)
    if count == 0:
        logger.warning("El informe HTML no carga Mermaid de un CDN: no se sustituye", extra={"file": html_file.name})
        return False
    html_file.write_text(replaced, encoding="utf-8")
    stub = html_file.parent / MERMAID_STUB_PATH
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_text(MERMAID_STUB, encoding="utf-8")
    return True


def _report_location(outputs_dir: Path, fmt: str) -> tuple[Path, str]:
    if fmt == "html":
        return outputs_dir / "html" / "comparacion", "index.html"
    return outputs_dir / fmt, f"comparacion{_EXTENSIONS[fmt]}"
