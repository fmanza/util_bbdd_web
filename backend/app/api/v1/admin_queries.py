"""``/api/v1/admin/queries``: queries nombradas de solo lectura por motor (solo ``admin``)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, Context, DbSession
from app.api.v1.explorer import named_query_out
from app.api.v1.schemas_explorer import NamedQueryCreate, NamedQueryOut, NamedQueryUpdate
from app.domain.explorer import sql

router = APIRouter(prefix="/admin/queries", tags=["admin"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    403: {"description": "Sin rol de administrador o CSRF no válido"},
}


@router.get("", response_model=list[NamedQueryOut], summary="Listar queries nombradas", responses=_ERRORS)
def list_queries(
    _: AdminUser, db: DbSession, db_type: Annotated[str | None, Query(max_length=32)] = None
) -> list[NamedQueryOut]:
    return [named_query_out(q) for q in sql.list_named_queries(db, db_type=db_type)]


@router.post(
    "",
    response_model=NamedQueryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear query nombrada",
    responses={**_ERRORS, 404: {"description": "Motor no soportado"}, 409: {"description": "Nombre repetido"},
               422: {"description": "Plantilla no válida o no es de solo lectura"}},
)  # fmt: skip
def create_query(body: NamedQueryCreate, admin: AdminUser, db: DbSession, ctx: Context) -> NamedQueryOut:
    """``sql_template`` usa ``{param}`` (sintaxis de util_bbdd); debe ser una única consulta de lectura."""
    query = sql.create_named_query(
        db, admin, db_type=body.db_type, name=body.name, description=body.description,
        sql_template=body.sql_template, ctx=ctx,
    )  # fmt: skip
    return named_query_out(query)


@router.patch(
    "/{query_id}",
    response_model=NamedQueryOut,
    summary="Editar query nombrada",
    responses={**_ERRORS, 404: {"description": "No existe"}, 409: {"description": "Nombre repetido"},
               422: {"description": "Plantilla no válida"}},
)  # fmt: skip
def update_query(query_id: int, body: NamedQueryUpdate, admin: AdminUser, db: DbSession, ctx: Context) -> NamedQueryOut:
    query = sql.get_named_query(db, query_id)
    updated = sql.update_named_query(
        db, admin, query, name=body.name, description=body.description, sql_template=body.sql_template, ctx=ctx
    )
    return named_query_out(updated)


@router.delete(
    "/{query_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Borrar query nombrada",
    responses={**_ERRORS, 404: {"description": "No existe"}},
)  # fmt: skip
def delete_query(query_id: int, admin: AdminUser, db: DbSession, ctx: Context) -> None:
    sql.delete_named_query(db, admin, sql.get_named_query(db, query_id), ctx=ctx)
