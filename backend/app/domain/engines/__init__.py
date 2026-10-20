"""Catálogo de motores (Fase 2): fachada de dominio sobre ``integrations/util_bbdd/catalog``."""

from __future__ import annotations

from app.domain.connections.errors import EngineNotFoundError
from app.integrations.util_bbdd.catalog import EngineDetail, UnknownEngineError, engine_detail, list_engines


def get_catalog() -> list[EngineDetail]:
    """Todos los motores de util_bbdd con su matriz de capacidades."""
    return list_engines()


def get_engine(db_type: str) -> EngineDetail:
    """Ficha de un motor.

    Raises:
        EngineNotFoundError: util_bbdd no lo soporta.
    """
    try:
        return engine_detail(db_type.strip().lower())
    except UnknownEngineError:
        raise EngineNotFoundError(f"util_bbdd no soporta el motor «{db_type}».") from None
