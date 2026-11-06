"""Orden de las listas paginadas: solo por columnas de una lista blanca, con desempate estable.

El parámetro ``sort`` de la API es un ``Literal`` por endpoint; aquí se traduce a una expresión SQL ya conocida, de
modo que el texto de la petición nunca llega al ``ORDER BY``. El desempate por la clave primaria hace que
``limit``/``offset`` no repitan ni salten filas entre páginas.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

SortOrder = Literal["asc", "desc"]


def order_by(
    columns: Mapping[str, Any],
    sort: str | None,
    order: SortOrder | None,
    *,
    default: Sequence[Any],
    tiebreak: Any,
) -> list[Any]:
    """Cláusulas ``ORDER BY``: ``columns[sort]`` en el sentido pedido (``asc`` por defecto) y el desempate; sin
    ``sort``, ``default`` (el orden de siempre de la lista).

    Raises:
        KeyError: ``sort`` no está en ``columns`` (no debería: la API lo valida con un ``Literal``).
    """
    if sort is None:
        return [*default, tiebreak]
    column = columns[sort]
    direction = column.desc() if order == "desc" else column.asc()
    tie = tiebreak.desc() if order == "desc" else tiebreak.asc()
    return [direction, tie]


def like_pattern(text: str) -> str:
    """``%texto%`` en minúsculas con ``%``, ``_`` y ``\\`` escapados (usar con ``escape="\\\\"``)."""
    escaped = text.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
