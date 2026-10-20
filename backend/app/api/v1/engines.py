"""``/api/v1/engines``: catálogo de motores de util_bbdd con su matriz de capacidades."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.api.v1.schemas import EngineDetailOut, EngineOut
from app.domain import engines

router = APIRouter(prefix="/engines", tags=["engines"])

_401: dict[int | str, dict[str, Any]] = {401: {"description": "No autenticado"}}


@router.get("", response_model=list[EngineOut], summary="Listar motores", responses=_401)
def list_engines(_: CurrentUser) -> list[EngineOut]:
    """Motores soportados por util_bbdd, drivers instalados y capacidades verificadas."""
    return [EngineOut.model_validate(e) for e in engines.get_catalog()]


@router.get(
    "/{db_type}",
    response_model=EngineDetailOut,
    summary="Ficha de un motor",
    responses={**_401, 404: {"description": "Motor no soportado"}},
)
def get_engine(db_type: str, _: CurrentUser) -> EngineDetailOut:
    """Descripción, versiones, drivers, características y parámetros de conexión del motor."""
    return EngineDetailOut.model_validate(engines.get_engine(db_type))
