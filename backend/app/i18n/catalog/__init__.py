"""Catálogo de mensajes del backend (ADR-015): un módulo por área, cada uno con ``ES`` y ``EN``.

Reglas (las vigila ``tests/unit/test_i18n.py``): mismas claves en los dos idiomas, mismos marcadores ``{nombre}`` y
ninguna clave repetida entre módulos. Las claves ``title.<code>`` son los títulos de las clases de :class:`AppError`;
el resto, ``<área>.<situación>``, que es también el ``code`` del *problem details*: no se renombran a la ligera.
"""

from __future__ import annotations

from types import ModuleType
from typing import Final

from app.i18n import Lang
from app.i18n.catalog import api, connections, core, identity, jobs, runs

MODULES: Final[tuple[ModuleType, ...]] = (core, api, identity, connections, runs, jobs)


def _merge(lang: str) -> dict[str, str]:
    merged: dict[str, str] = {}
    for module in MODULES:
        merged.update(getattr(module, lang.upper()))
    return merged


CATALOG: Final[dict[Lang, dict[str, str]]] = {"es": _merge("es"), "en": _merge("en")}
