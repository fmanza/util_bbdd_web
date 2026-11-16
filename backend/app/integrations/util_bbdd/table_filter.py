"""Filtro de tablas por patrones de util_bbdd 5.9.0 (``util_bbdd.metadata.TableFilter``) para migración y volcado.

La documentación lo pasa como ``imprimir["filtro"]`` (``documentation.py``); el plan de migración
(``MigrationPlanner.plan(table_filter=...)``) y el volcado (``DumpConfig.table_filter``) reciben el objeto. Los
patrones llegan ya validados y normalizados por los parámetros de la operación (``normalize_filter_patterns``).
"""

from __future__ import annotations

from typing import Any


def patterns(value: str | None) -> list[str]:
    """Patrones separados por comas, sin vacíos."""
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def build_table_filter(include: str | None, exclude: str | None) -> Any | None:
    """``TableFilter`` de util_bbdd, o ``None`` sin patrones (se migra o vuelca todo)."""
    from util_bbdd.metadata import TableFilter

    return TableFilter.from_patterns(patterns(include), patterns(exclude))


def filter_summary(table_filter: Any | None) -> dict[str, list[str]] | None:
    """``{"include": [...], "exclude": [...]}`` para el visor, o ``None`` sin filtro."""
    if table_filter is None:
        return None
    return {"include": list(table_filter.include), "exclude": list(table_filter.exclude)}
