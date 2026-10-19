"""Capa anticorrupción con util_bbdd (ADR-006).

Es el **único** paquete de la aplicación que importa ``util_bbdd`` (lo comprueba
``tests/unit/test_architecture.py``). El resto del backend depende de las funciones y tipos propios que se exponen
aquí, de modo que una versión MAJOR de la librería solo obliga a tocar esta capa.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def library_version() -> str | None:
    """Versión instalada de util_bbdd, o None si no está instalada."""
    try:
        return version("util_bbdd")
    except PackageNotFoundError:
        return None


def supported_db_types() -> list[str]:
    """Motores que declara util_bbdd (base del catálogo de la Fase 2)."""
    from util_bbdd import SyncDatabaseManager

    return list(SyncDatabaseManager.get_supported_db_types())
