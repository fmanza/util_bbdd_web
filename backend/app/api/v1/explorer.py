"""Explorador de metadatos y queries nombradas por conexión, y SQL libre por conexión de proyecto (Fase 4)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Path, Query, status

from app.api.deps import Context, CurrentUser, DbSession, SettingsDep
from app.api.v1.schemas_explorer import (
    DdlOut,
    FreeSqlIn,
    NamedQueryOut,
    NamedQueryRun,
    ObjectKind,
    QueryResultOut,
    SchemaList,
    SchemaSummary,
    SqlCapabilities,
    SqlConnection,
    TableDetail,
)
from app.db.models import NamedQuery
from app.domain.connections.service import get_visible
from app.domain.explorer import metadata, sql
from app.domain.explorer.sql import QueryResult
from app.domain.projects.service import get_membership, list_project_connections

router = APIRouter(prefix="/connections/{connection_id}", tags=["explorer"])
project_router = APIRouter(prefix="/projects/{project_id}", tags=["explorer"])

SchemaName = Annotated[str, Path(min_length=1, max_length=128, pattern=r"^[^\x00-\x1f]+$")]
_READ: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    404: {"description": "Conexión no visible u objeto inexistente"},
    429: {"description": "Demasiadas consultas en curso"},
    502: {"description": "No se pudo consultar la BD (código saneado)"},
    504: {"description": "La BD no respondió a tiempo"},
}


def _result(result: QueryResult) -> QueryResultOut:
    return QueryResultOut(
        columns=result.columns,
        rows=result.rows,
        truncated=result.truncated,
        row_count=result.row_count,
        duration_ms=result.duration_ms,
    )


def named_query_out(query: NamedQuery) -> NamedQueryOut:
    return NamedQueryOut(
        id=query.id,
        db_type=query.db_type,
        name=query.name,
        description=query.description,
        params=sql.query_params(query),
        sql_template=query.sql_template,
        created_at=query.created_at,
        updated_at=query.updated_at,
    )


# --- metadatos ---------------------------------------------------------------------------------------------------


@router.get("/metadata/schemas", response_model=SchemaList, summary="Schemas de la conexión", responses=_READ)
def list_schemas(connection_id: int, user: CurrentUser, db: DbSession, settings: SettingsDep) -> SchemaList:
    """Schemas visibles para el usuario de la conexión; ``system`` marca los del motor y ``cached`` los que ya tienen
    snapshot."""
    connection = get_visible(db, user, connection_id)
    data = metadata.list_schemas(db, connection, settings)
    cached = set(metadata.cached_schemas(db, connection))
    return SchemaList(
        default=data.get("default"),
        schemas=[{**s, "cached": s["name"] in cached} for s in data.get("schemas", [])],
    )


@router.get("/metadata/schemas/{schema}", response_model=SchemaSummary, summary="Árbol de un schema", responses=_READ)
def get_schema(
    connection_id: int,
    schema: SchemaName,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    refresh: Annotated[bool, Query(description="Vuelve a leer el catálogo aunque haya caché")] = False,
) -> SchemaSummary:
    """Tablas, vistas y rutinas del schema desde la caché (o leídas con ``get_schema_metadata``)."""
    connection = get_visible(db, user, connection_id)
    snapshot = metadata.get_snapshot(db, connection, schema, settings, refresh=refresh)
    data = metadata.summary(snapshot)
    return SchemaSummary(
        engine=data["engine"],
        schema_name=data["schema"] or schema,
        database=data["database"],
        fetched_at=data["fetched_at"],
        size_bytes=data["size_bytes"],
        tables=data["tables"],
        views=data["views"],
        routines=data["routines"],
    )


@router.delete(
    "/metadata/schemas/{schema}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Invalidar la caché del schema",
    responses={401: _READ[401], 404: _READ[404]},
)
def invalidate_schema(connection_id: int, schema: SchemaName, user: CurrentUser, db: DbSession) -> None:
    metadata.invalidate(db, get_visible(db, user, connection_id), schema)


@router.get(
    "/metadata/schemas/{schema}/tables/{table}",
    response_model=TableDetail,
    summary="Detalle de una tabla",
    responses=_READ,
)
def get_table(
    connection_id: int, schema: SchemaName, table: SchemaName, user: CurrentUser, db: DbSession, settings: SettingsDep
) -> TableDetail:
    connection = get_visible(db, user, connection_id)
    snapshot = metadata.get_snapshot(db, connection, schema, settings)
    return TableDetail.model_validate(metadata.table_detail(snapshot, table))


@router.get("/metadata/schemas/{schema}/ddl", response_model=DdlOut, summary="DDL de un objeto", responses=_READ)
def get_ddl(
    connection_id: int,
    schema: SchemaName,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    kind: Annotated[ObjectKind, Query()],
    name: Annotated[str, Query(min_length=1, max_length=128)],
) -> DdlOut:
    """``CREATE`` de una tabla, vista o rutina (``util_bbdd.metadata.ddl``)."""
    connection = get_visible(db, user, connection_id)
    return DdlOut(kind=kind, name=name, ddl=metadata.object_ddl(db, connection, schema, kind, name, settings))


# --- queries nombradas -------------------------------------------------------------------------------------------


@router.get(
    "/queries", response_model=list[NamedQueryOut], summary="Queries nombradas del motor",
    responses={401: _READ[401], 404: _READ[404]},
)  # fmt: skip
def list_queries(connection_id: int, user: CurrentUser, db: DbSession) -> list[NamedQueryOut]:
    connection = get_visible(db, user, connection_id)
    return [named_query_out(q) for q in sql.list_named_queries(db, db_type=connection.db_type)]


@router.post(
    "/queries/{query_id}/run",
    response_model=QueryResultOut,
    summary="Ejecutar una query nombrada",
    responses={**_READ, 422: {"description": "Parámetros no válidos o SQL no admitido"}},
)
def run_query(
    connection_id: int,
    query_id: int,
    body: NamedQueryRun,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    ctx: Context,
) -> QueryResultOut:
    """Resuelve la plantilla con util_bbdd, valida el SQL final y lo ejecuta en una transacción de solo lectura."""
    connection = get_visible(db, user, connection_id)
    query = sql.get_named_query(db, query_id)
    result = sql.run_named_query(
        db, user, connection, query, params=body.params, limit=body.limit, settings=settings, ctx=ctx
    )
    return _result(result)


# --- SQL libre ---------------------------------------------------------------------------------------------------


@project_router.get(
    "/sql", response_model=SqlCapabilities, summary="¿Puedo usar SQL libre en el proyecto?",
    responses={401: _READ[401], 404: {"description": "No eres miembro"}},
)  # fmt: skip
def sql_capabilities(project_id: int, user: CurrentUser, db: DbSession) -> SqlCapabilities:
    """Permiso del usuario y conexiones del proyecto aptas (``read_only`` y motor con guardián)."""
    membership = get_membership(db, user, project_id)
    reason = None
    if not membership.can("editor"):
        reason = "role"
    elif not user.can_run_sql:
        reason = "permission"
    connections = [
        SqlConnection(
            alias=link.alias,
            connection_name=link.connection.name,
            db_type=link.connection.db_type,
            read_only=link.connection.read_only,
            supported=sql.free_sql_supported(link.connection.db_type),
            read_only_transaction=sql.read_only_transaction(link.connection.db_type),
        )
        for link in list_project_connections(db, membership.project)
    ]
    return SqlCapabilities(allowed=reason is None, reason=reason, connections=connections)


@project_router.post(
    "/connections/{alias}/sql",
    response_model=QueryResultOut,
    summary="Ejecutar SQL libre",
    responses={
        **_READ,
        403: {"description": "Sin permiso de SQL libre, no eres editor o CSRF no válido"},
        409: {"description": "La conexión no es de solo lectura"},
        422: {"description": "No es una única consulta de lectura, o el motor la rechaza"},
    },
)
def run_sql(
    project_id: int, alias: str, body: FreeSqlIn, user: CurrentUser, db: DbSession, settings: SettingsDep, ctx: Context
) -> QueryResultOut:
    """Consulta de lectura sobre una conexión ``read_only`` del proyecto, con límite de filas y timeout. Se audita."""
    return _result(
        sql.run_free_sql(
            db, user, project_id=project_id, alias=alias, sql=body.sql, limit=body.limit, settings=settings, ctx=ctx
        )
    )
