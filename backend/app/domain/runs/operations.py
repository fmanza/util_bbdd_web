"""Catálogo de operaciones que se pueden lanzar como ejecución y sus parámetros.

Cada operación declara un modelo Pydantic (``extra="forbid"``) que valida los parámetros al encolar; los campos con
``ubw_kind="connection"`` son alias de una conexión del proyecto. La implementación vive en ``app/jobs/operations``.
Los campos con ``ubw_group`` se agrupan en el formulario; los ``Literal`` se ofrecen como opciones.
Fase 3: ``noop``. Fase 5: ``documentation`` y ``relationship_graph``. Fase 6: ``compare``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.domain.runs.errors import RunParamsError, UnknownOperationError

ALIAS_PATTERN = r"^[a-z0-9_-]{1,32}$"
ParamType = Literal["string", "integer", "float", "boolean", "connection"]


class NoopParams(BaseModel):
    """Job de prueba: pasos con espera, fallo opcional y prueba opcional de una conexión del proyecto."""

    model_config = ConfigDict(extra="forbid")

    steps: int = Field(default=3, ge=1, le=20, description="Número de pasos (progreso por paso).")
    step_seconds: float = Field(default=1.0, ge=0, le=30, description="Espera de cada paso, en segundos.")
    fail: bool = Field(default=False, description="Termina en error a propósito (prueba de fallos).")
    connection: str | None = Field(
        default=None,
        pattern=ALIAS_PATTERN,
        description="Alias de una conexión del proyecto que se prueba desde el worker (opcional).",
        json_schema_extra={"ubw_kind": "connection"},
    )


def _connection(description: str) -> Any:
    return Field(pattern=ALIAS_PATTERN, description=description, json_schema_extra={"ubw_kind": "connection"})


def _group(group: str, default: Any, description: str, **extra: Any) -> Any:
    return Field(default=default, description=description, json_schema_extra={"ubw_group": group}, **extra)


#: Nombres de schema y tabla: identificadores (con ``$``, ``#``, ``.``, ``-`` y espacios), sin comillas ni ``;``, porque
#: util_bbdd puede usarlos en el SQL de sus consultas de catálogo.
OBJECT_NAME_PATTERN = r"^[\w$#][\w$#. -]{0,127}$"

SCHEMA_DESCRIPTION = (
    "Schema a documentar; vacío = el de la conexión. MySQL/MariaDB: la base de datos. Oracle: solo el del usuario de "
    "la conexión."
)


class DocumentationParams(BaseModel):
    """Documentación de un schema con ``DatabaseDocumentation`` de util_bbdd (Word, Excel y/o HTML)."""

    connection: str = _connection("Alias de la conexión del proyecto que se documenta.")
    schema_name: str | None = Field(
        default=None, pattern=OBJECT_NAME_PATTERN, description=SCHEMA_DESCRIPTION, alias="schema"
    )
    word: bool = _group("formats", True, "Documento Word (.docx).")
    excel: bool = _group("formats", True, "Libro Excel (.xlsx).")
    html: bool = _group("formats", True, "Sitio HTML navegable.")
    tables: bool = _group("tables", True, "Documentar las tablas.")
    table_columns: bool = _group("tables", True, "Columnas de cada tabla.")
    table_keys: bool = _group("tables", True, "Claves primarias, foráneas y únicas.")
    table_indexes: bool = _group("tables", True, "Índices.")
    table_ddl: bool = _group("tables", False, "DDL de cada tabla.")
    views: bool = _group("views", True, "Documentar las vistas (columnas).")
    view_ddl: bool = _group("views", False, "DDL de cada vista.")
    routines: bool = _group("routines", False, "Procedimientos y funciones.")
    database_info: bool = _group("extra", True, "Versión y datos generales de la BD.")
    storage: bool = _group("extra", False, "Inventario de almacenamiento.")
    engine_conditions: bool = _group("extra", False, "Condiciones del motor (readiness).")
    charset: bool = _group("extra", False, "Charset y collation.")
    graphs: bool = _group("graphs", True, "Diagramas de relaciones en Word y HTML (necesitan Graphviz).")
    graph_depth: int = _group("graphs", 1, "Niveles de relación en cada diagrama.", ge=1, le=3)
    graph_direction: Literal["both", "outgoing", "incoming"] = _group(
        "graphs", "both", "Relaciones que muestra cada diagrama."
    )
    tables_per_document: int = _group("layout", 50, "Tablas por documento Word.", ge=1, le=500)
    html_items_per_page: int = _group("layout", 15, "Elementos por página del índice HTML.", ge=5, le=100)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def _one_format(self) -> DocumentationParams:
        if not (self.word or self.excel or self.html):
            raise ValueError("Elige al menos un formato (Word, Excel o HTML).")
        return self


class RelationshipGraphParams(BaseModel):
    """Grafo de relaciones de una tabla (o de todas) con ``GraphvizRelationshipGraphExt`` de util_bbdd."""

    connection: str = _connection("Alias de la conexión del proyecto.")
    schema_name: str | None = Field(
        default=None, pattern=OBJECT_NAME_PATTERN, description=SCHEMA_DESCRIPTION, alias="schema"
    )
    table: str | None = Field(
        default=None,
        pattern=OBJECT_NAME_PATTERN,
        description="Tabla central; vacío = un grafo por cada tabla con relaciones.",
    )
    max_depth: int = _group("graph", 1, "Niveles de relación.", ge=1, le=5)
    direction: Literal["both", "outgoing", "incoming"] = _group("graph", "both", "Relaciones a mostrar.")
    column_mode: Literal["relations", "compact", "all"] = _group(
        "graph", "relations", "Columnas en cada tabla: solo las de relación, ninguna o todas."
    )
    max_columns: int = _group("graph", 8, "Columnas máximas por tabla.", ge=1, le=50)
    show_data_types: bool = _group("graph", False, "Mostrar el tipo de cada columna.")
    max_subnodes: int = _group(
        "graph", 10, "Tablas relacionadas por imagen (las demás van en otras imágenes).", ge=2, le=50
    )
    format: Literal["svg", "png"] = _group("graph", "svg", "Formato de imagen.")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


COMPARE_SCHEMA_DESCRIPTION = (
    "Schema; vacío = el de la conexión. MySQL/MariaDB: la base de datos. Oracle: el usuario dueño de las tablas."
)


class CompareParams(BaseModel):
    """Comparación de esquemas con ``SchemaComparator`` de util_bbdd e informes con ``SchemaDiffReporter``."""

    source_connection: str = _connection("Conexión origen (la referencia).")
    source_schema: str | None = Field(default=None, pattern=OBJECT_NAME_PATTERN, description=COMPARE_SCHEMA_DESCRIPTION)
    target_connection: str = _connection("Conexión destino (la que se compara con el origen).")
    target_schema: str | None = Field(default=None, pattern=OBJECT_NAME_PATTERN, description=COMPARE_SCHEMA_DESCRIPTION)
    tables: bool = _group("scope", True, "Tablas y columnas.")
    indexes: bool = _group("scope", True, "Índices (con tablas).")
    foreign_keys: bool = _group("scope", True, "Claves foráneas (con tablas).")
    comments: bool = _group("scope", True, "Comentarios de tablas y columnas (con tablas).")
    views: bool = _group("scope", True, "Vistas.")
    routines: bool = _group("scope", False, "Procedimientos y funciones (no en HSQLDB ni SQLite).")
    html: bool = _group("reports", True, "Informe HTML.")
    excel: bool = _group("reports", True, "Libro Excel.")
    word: bool = _group("reports", False, "Documento Word.")
    markdown: bool = _group("reports", True, "Markdown.")
    sql: bool = _group("reports", True, "Script SQL de nivelación (solo se genera; no se ejecuta).")
    sql_dialect: Literal["auto", "generic", "mariadb", "mysql", "postgresql", "sqlserver", "oracle", "sqlite"] = _group(
        "reports", "auto", "Dialecto del script SQL; auto = el del motor destino."
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _something_to_compare(self) -> CompareParams:
        if not (self.tables or self.views or self.routines):
            raise ValueError("Elige al menos tablas, vistas o rutinas.")
        return self


@dataclass(frozen=True)
class OperationParam:
    """Parámetro de una operación tal como lo ve el formulario de lanzamiento."""

    name: str
    type: ParamType
    required: bool
    default: Any
    description: str
    minimum: float | None
    maximum: float | None
    options: list[str] | None = None
    group: str | None = None


@dataclass(frozen=True)
class OperationSpec:
    """Operación lanzable."""

    name: str
    title: str
    description: str
    model: type[BaseModel]

    @property
    def params(self) -> list[OperationParam]:
        schema = self.model.model_json_schema(by_alias=True)
        required = set(schema.get("required", []))
        result = []
        for name, prop in schema.get("properties", {}).items():
            raw_type = prop.get("type") or next(
                (p.get("type") for p in prop.get("anyOf", []) if p.get("type") != "null"), "string"
            )
            options = prop.get("enum")
            kind: ParamType
            if prop.get("ubw_kind") == "connection":
                kind = "connection"
            elif raw_type == "integer":
                kind = "integer"
            elif raw_type == "number":
                kind = "float"
            elif raw_type == "boolean":
                kind = "boolean"
            else:
                kind = "string"
            result.append(
                OperationParam(
                    name=name,
                    type=kind,
                    required=name in required,
                    default=prop.get("default"),
                    description=str(prop.get("description", "")),
                    minimum=prop.get("minimum"),
                    maximum=prop.get("maximum"),
                    options=[str(o) for o in options] if options else None,
                    group=prop.get("ubw_group"),
                )
            )
        return result

    def connection_params(self, params: dict[str, Any]) -> list[str]:
        """Alias de conexión usados en ``params``."""
        names = {p.name for p in self.params if p.type == "connection"}
        return [str(params[name]) for name in names if params.get(name)]


OPERATIONS: dict[str, OperationSpec] = {
    "noop": OperationSpec(
        name="noop",
        title="Prueba del motor de ejecuciones",
        description="Simula una ejecución con pasos y artefactos de ejemplo (Markdown, HTML, SQL y SVG).",
        model=NoopParams,
    ),
    "documentation": OperationSpec(
        name="documentation",
        title="Documentación de la base de datos",
        description="Documenta un schema en Word, Excel y/o HTML con util_bbdd (tablas, vistas, rutinas y diagramas).",
        model=DocumentationParams,
    ),
    "relationship_graph": OperationSpec(
        name="relationship_graph",
        title="Grafo de relaciones",
        description="Diagrama de las claves foráneas alrededor de una tabla (o de todas) con Graphviz.",
        model=RelationshipGraphParams,
    ),
    "compare": OperationSpec(
        name="compare",
        title="Comparación de esquemas",
        description="Compara dos conexiones o schemas con util_bbdd: visor del diff e informes HTML, Excel, Word, "
        "Markdown y SQL.",
        model=CompareParams,
    ),
}


def get_operation(name: str) -> OperationSpec:
    """Operación por nombre.

    Raises:
        UnknownOperationError: No está en el catálogo.
    """
    spec = OPERATIONS.get(name)
    if spec is None:
        raise UnknownOperationError(f"No existe la operación «{name}».")
    return spec


def validate_params(spec: OperationSpec, params: dict[str, Any]) -> dict[str, Any]:
    """Parámetros normalizados (con valores por defecto) o error por campo.

    Raises:
        RunParamsError: Con ``errors`` en el formato de FastAPI (``loc`` = ``["body", "params", campo]``).
    """
    try:
        model = spec.model.model_validate(params)
    except ValidationError as exc:
        errors: list[dict[str, Any]] = [
            {"loc": ["body", "params", *[str(p) for p in e["loc"]]], "msg": str(e["msg"]), "type": e["type"]}
            for e in exc.errors()
        ]
        raise RunParamsError(str(errors[0]["msg"]) if errors else None, errors=errors) from None
    return model.model_dump(mode="json", by_alias=True)
