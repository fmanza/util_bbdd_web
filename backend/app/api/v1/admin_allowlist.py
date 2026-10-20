"""``/api/v1/admin/allowlist``: destinos permitidos para las conexiones salientes (solo ``admin``, anti-SSRF)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from app.api.deps import AdminUser, Context, DbSession
from app.api.v1.schemas import AllowlistEntryIn, AllowlistEntryOut
from app.domain.connections import allowlist

router = APIRouter(prefix="/admin/allowlist", tags=["admin"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    403: {"description": "Sin rol de administrador o token CSRF no válido"},
}


@router.get("", response_model=list[AllowlistEntryOut], summary="Listar destinos permitidos", responses=_ERRORS)
def list_allowlist(_: AdminUser, db: DbSession) -> list[AllowlistEntryOut]:
    """Redes CIDR y nombres de host a los que se puede conectar. Vacía: ningún destino permitido."""
    return [AllowlistEntryOut.model_validate(e) for e in allowlist.list_entries(db)]


@router.post(
    "",
    response_model=AllowlistEntryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Añadir destino permitido",
    responses={**_ERRORS, 409: {"description": "Ya existe"}, 422: {"description": "Patrón no válido"}},
)
def add_allowlist_entry(body: AllowlistEntryIn, admin: AdminUser, db: DbSession, ctx: Context) -> AllowlistEntryOut:
    """Añade una red CIDR (``10.0.0.0/8``), IP, nombre de host o comodín (``*.empresa.local``)."""
    entry = allowlist.add_entry(db, pattern=body.pattern, description=body.description, actor_id=admin.id, ctx=ctx)
    return AllowlistEntryOut.model_validate(entry)


@router.delete(
    "/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Quitar destino permitido",
    responses={**_ERRORS, 404: {"description": "No existe"}},
)
def delete_allowlist_entry(entry_id: int, admin: AdminUser, db: DbSession, ctx: Context) -> None:
    """Quita un destino; las conexiones que lo usen dejarán de poder probarse."""
    allowlist.delete_entry(db, entry_id, actor_id=admin.id, ctx=ctx)
