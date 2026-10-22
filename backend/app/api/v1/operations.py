"""``/api/v1/operations``: catálogo de operaciones lanzables y sus parámetros."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.api.v1.schemas_projects import OperationOut, OperationParamOut
from app.domain.runs.operations import OPERATIONS

router = APIRouter(prefix="/operations", tags=["runs"])

_401: dict[int | str, dict[str, Any]] = {401: {"description": "No autenticado"}}


@router.get("", response_model=list[OperationOut], summary="Listar operaciones", responses=_401)
def list_operations(_: CurrentUser) -> list[OperationOut]:
    """Operaciones que se pueden lanzar como ejecución; ``form=false`` se lanzan desde otra pantalla."""
    return [
        OperationOut(
            name=spec.name,
            title=spec.title,
            description=spec.description,
            params=[OperationParamOut.model_validate(p) for p in spec.params],
            form=spec.form,
        )
        for spec in OPERATIONS.values()
    ]
