"""Catálogo de operaciones que se pueden lanzar como ejecución y sus parámetros.

Cada operación declara un modelo Pydantic (``extra="forbid"``) que valida los parámetros al encolar; los campos con
``ubw_kind="connection"`` son alias de una conexión del proyecto y los ``ubw_kind="template"``, el id de una plantilla
de documento (``ubw_template_kind``: ``word`` o ``excel``, ADR-011). La implementación vive en ``app/jobs/operations``.
Los campos con ``ubw_group`` se agrupan en el formulario; los ``Literal`` se ofrecen como opciones.
Fase 3: ``noop``. Fase 5: ``documentation`` y ``relationship_graph``. Fase 6: ``compare``.
Fase 7: ``migrate_plan`` y ``migrate_apply`` (este no sale en el formulario genérico: se lanza desde el plan).
Fase 8: ``dump_preview`` (modo seco) y ``dump_apply`` (se lanza desde la vista previa); desde la 1.4.0,
``dump_restore`` (se lanza desde un volcado con constraints sin restaurar, o lo encola el worker).
Fase 9: ``bulk_preview`` y ``bulk_apply`` (carga desde fichero; las dos se lanzan desde el asistente de carga).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.domain.runs.errors import RunParamsError, UnknownOperationError

ALIAS_PATTERN = r"^[a-z0-9_-]{1,32}$"
ParamType = Literal["string", "integer", "float", "boolean", "connection", "template"]
ULID_PATTERN = r"^[0-9A-HJKMNP-TV-Z]{26}$"


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


def _template(kind: str, description: str) -> Any:
    return Field(
        default=None,
        pattern=ULID_PATTERN,
        description=description,
        json_schema_extra={"ubw_group": "templates", "ubw_kind": "template", "ubw_template_kind": kind},
    )


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
    graph_columns: Literal["relations_first", "relations", "all", "compact"] = _group(
        "graphs",
        "relations_first",
        "Columnas en cada tabla del diagrama: primero las de relación y luego el resto, solo las de relación, todas "
        "o ninguna.",
    )
    graph_max_columns: int = _group("graphs", 8, "Columnas máximas por tabla del diagrama.", ge=1, le=50)
    graph_data_types: bool = _group("graphs", False, "Mostrar el tipo de cada columna en el diagrama.")
    graph_orthogonal: bool = _group(
        "graphs",
        True,
        "Relaciones en ángulo recto; desactívalo (curvas) si Graphviz no puede dibujar algún diagrama (GAPS G39).",
    )
    tables_per_document: int = _group("layout", 50, "Tablas por documento Word.", ge=1, le=500)
    html_items_per_page: int = _group("layout", 15, "Elementos por página del índice HTML.", ge=5, le=100)
    word_template: str | None = _template(
        "word",
        "Plantilla Word del proyecto o global; vacío = formato por defecto. Con plantilla se respeta su "
        "orientación y su contenido se repite en cada documento.",
    )
    excel_template: str | None = _template(
        "excel",
        "Plantilla Excel del proyecto o global (tema, encabezado y pie, estilo de tabla); vacío = formato por defecto.",
    )

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def _one_format(self) -> DocumentationParams:
        if not (self.word or self.excel or self.html):
            raise ValueError("Elige al menos un formato (Word, Excel o HTML).")
        # Una plantilla de un formato que no se genera no se usa: se descarta para no bloquear su borrado.
        if not self.word:
            self.word_template = None
        if not self.excel:
            self.excel_template = None
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
    column_mode: Literal["relations", "relations_first", "compact", "all"] = _group(
        "graph",
        "relations",
        "Columnas en cada tabla: solo las de relación, primero las de relación y luego el resto, ninguna o todas.",
    )
    max_columns: int = _group("graph", 8, "Columnas máximas por tabla.", ge=1, le=50)
    show_data_types: bool = _group("graph", False, "Mostrar el tipo de cada columna.")
    orthogonal_edges: bool = _group(
        "graph", True, "Relaciones en ángulo recto; desactívalo (curvas) si Graphviz no puede dibujar el grafo."
    )
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


RUN_ID_PATTERN = r"^[0-9A-HJKMNP-TV-Z]{26}$"
_CHARSET_PATTERN = r"^[A-Za-z0-9_]{1,64}$"
MigrationEngine = Literal["mariadb", "mysql", "sqlserver", "postgresql", "oracle"]


class MigratePlanParams(BaseModel):
    """Plan de migración DDL con ``MigrationPlanner`` de util_bbdd: solo lee el origen (ADR-008)."""

    source_connection: str = _connection("Conexión origen (Oracle, MariaDB, MySQL, SQL Server o PostgreSQL).")
    source_schema: str | None = Field(
        default=None, pattern=OBJECT_NAME_PATTERN, description="Schema a migrar; vacío = el de la conexión."
    )
    target_engine: MigrationEngine = Field(description="Motor destino (distinto del origen).")
    view_strategy: Literal["auto", "transpile", "passthrough"] = _group(
        "general", "auto", "Vistas: reescribirlas al dialecto destino (auto/transpile) o copiarlas sin cambios."
    )
    number_fallback: Literal["DOUBLE", "DECIMAL(38,10)", "DECIMAL(18,4)"] = _group(
        "general", "DOUBLE", "Tipo destino para NUMBER de Oracle sin precisión (origen Oracle)."
    )
    charset: str | None = _group("mysql", None, "CHARACTER SET (destino MariaDB/MySQL).", pattern=_CHARSET_PATTERN)
    collation: str | None = _group("mysql", None, "COLLATE (destino MariaDB/MySQL).", pattern=_CHARSET_PATTERN)
    storage_engine: str = _group(
        "mysql", "InnoDB", "Motor de almacenamiento (destino MariaDB/MySQL).", pattern=r"^[A-Za-z]{1,32}$"
    )
    int_display_width: int = _group("mysql", 11, "Ancho de INT (Oracle → MariaDB; 0 = sin ancho).", ge=0, le=255)
    sql_server_collation: str | None = _group(
        "sqlserver", None, "COLLATE por columna (destino SQL Server); vacío = la de la BD.", pattern=_CHARSET_PATTERN
    )
    pg_schema: str | None = _group(
        "postgresql", None, "Schema destino (destino PostgreSQL; emite SET search_path).", pattern=OBJECT_NAME_PATTERN
    )
    oracle_identity_mode: Literal["sequence_trigger", "identity"] = _group(
        "oracle", "sequence_trigger", "Autoincrementales en destino Oracle: secuencia + trigger o IDENTITY."
    )

    model_config = ConfigDict(extra="forbid")


class MigrateApplyParams(BaseModel):
    """Modo seco o aplicación de un plan ``migrate_plan`` en una conexión destino (ADR-008).

    ``apply`` exige un ``dry_run_run`` correcto reciente del mismo plan y destino y ``confirm`` igual al alias.
    """

    plan_run: str = Field(pattern=RUN_ID_PATTERN, description="Ejecución migrate_plan que se aplica.")
    target_connection: str = _connection("Conexión destino (no de solo lectura, del motor del plan).")
    mode: Literal["dry_run", "apply"] = Field(default="dry_run", description="Modo seco (sin cambios) o aplicar.")
    dry_run_run: str | None = Field(
        default=None, pattern=RUN_ID_PATTERN, description="Modo seco correcto previo (obligatorio para aplicar)."
    )
    confirm: str | None = Field(
        default=None, max_length=64, description="Alias de la conexión destino escrito a mano (para aplicar)."
    )

    model_config = ConfigDict(extra="forbid")


#: Lista de tablas separadas por comas (nombres de objeto, sin comillas ni ``;``). Sin ``.``: las tablas se buscan en
#: el schema del formulario, no como ``schema.tabla``.
TABLES_PATTERN = r"^\s*[\w$#-]+(\s*,\s*[\w$#-]+)*\s*$"


class DumpPreviewParams(BaseModel):
    """Vista previa (modo seco) de un volcado de datos: solo lee origen y destino (ADR-009)."""

    source_connection: str = _connection("Conexión origen (de donde se leen las filas).")
    source_schema: str | None = Field(
        default=None, pattern=OBJECT_NAME_PATTERN, description="Schema origen; vacío = el de la conexión."
    )
    target_connection: str = _connection("Conexión destino (donde se escriben; sus tablas deben existir).")
    target_schema: str | None = Field(
        default=None, pattern=OBJECT_NAME_PATTERN, description="Schema destino; vacío = el de la conexión."
    )
    tables: str | None = Field(
        default=None,
        max_length=4000,
        pattern=TABLES_PATTERN,
        description="Tablas a volcar separadas por comas; vacío = todas las del origen.",
    )
    truncate_target: bool = _group(
        "load", False, "Vaciar las tablas destino antes de cargar (si no, las filas se añaden)."
    )
    sync_pk_sequences: bool = _group("load", True, "Ajustar secuencias/IDENTITY/AUTO_INCREMENT al máximo cargado.")
    on_error: Literal["raise", "isolate"] = _group(
        "errors", "raise", "Filas que el destino no admite: fallar la tabla o apartarlas a un CSV de rechazos."
    )
    max_rejects: int | None = _group(
        "errors", None, "Rechazos máximos por tabla (con «apartar»); vacío = sin límite.", ge=1, le=1_000_000
    )
    chunk_size: int = _group("performance", 5000, "Filas por lote de lectura y escritura.", ge=100, le=100_000)
    max_parallel_tables: int = _group("performance", 1, "Tablas independientes en paralelo.", ge=1, le=4)
    manage_indexes: Literal["none", "secondary"] = _group(
        "performance", "none", "Desactivar los índices secundarios no únicos durante la carga y reconstruirlos."
    )

    model_config = ConfigDict(extra="forbid")


class DumpApplyParams(BaseModel):
    """Volcado de datos con los parámetros de una vista previa correcta y reciente (ADR-009)."""

    preview_run: str = Field(pattern=RUN_ID_PATTERN, description="Vista previa dump_preview que se ejecuta.")
    confirm: str = Field(max_length=64, description="Alias de la conexión destino escrito a mano.")
    confirm_truncate: str | None = Field(
        default=None, max_length=16, description="«VACIAR» escrito a mano si la vista previa vacía el destino."
    )

    model_config = ConfigDict(extra="forbid")


class DumpRestoreParams(BaseModel):
    """Reactivar las constraints que un volcado interrumpido dejó desactivadas (G31, ADR-009 enmendado)."""

    dump_run: str = Field(pattern=RUN_ID_PATTERN, description="Volcado dump_apply con constraints sin restaurar.")
    confirm: str = Field(max_length=64, description="Alias de la conexión destino escrito a mano.")

    model_config = ConfigDict(extra="forbid")


#: Nombre de tabla (sin ``.``: el schema va aparte) y de columna (admite espacios, como en una cabecera de CSV).
TABLE_PATTERN = r"^[\w$#][\w$# -]{0,127}$"
COLUMN_PATTERN = r"^[^\x00-\x1f]{1,128}$"


class BulkPreviewParams(BaseModel):
    """Vista previa (modo seco) de una carga desde un fichero subido: valida, cuenta y genera el SQL (ADR-010)."""

    upload: str = Field(pattern=RUN_ID_PATTERN, description="Fichero subido al proyecto.")
    target_connection: str = _connection("Conexión destino.")
    target_schema: str | None = Field(
        default=None, pattern=OBJECT_NAME_PATTERN, description="Schema destino; vacío = el de la conexión."
    )
    table: str = Field(pattern=TABLE_PATTERN, description="Tabla destino.")
    operation: Literal["insert", "update", "delete"] = Field(description="Operación por fila del fichero.")
    mapping: dict[Annotated[str, Field(pattern=COLUMN_PATTERN)], Annotated[str, Field(pattern=COLUMN_PATTERN)]] = Field(
        default_factory=dict, max_length=500, description="Columna del fichero → columna de la tabla."
    )
    sheet: str | None = Field(default=None, max_length=100, description="Hoja del Excel; vacío = la primera.")
    delimiter: Literal[",", ";", "\t", "|"] | None = Field(default=None, description="Separador del CSV.")
    encoding: Literal["utf-8", "cp1252", "latin-1"] | None = Field(default=None, description="Codificación del CSV.")
    on_error: Literal["raise", "isolate"] = Field(default="raise", description="Filas que el destino no admite.")
    max_rejects: int | None = Field(default=None, ge=1, le=1_000_000, description="Rechazos máximos.")
    parallel: bool = Field(default=False, description="Plan paralelo automático (deja de ser atómico).")
    chunk_size: int | None = Field(default=None, ge=100, le=100_000, description="Filas por lote.")
    override_identity: bool = Field(
        default=False,
        description="Insert en PostgreSQL: conservar los valores del fichero en columnas GENERATED ALWAYS AS IDENTITY.",
    )
    sync_pk_sequences: bool = Field(
        default=True, description="Insert: ajustar el contador de la PK (secuencia/IDENTITY/AUTO_INCREMENT) al máximo."
    )

    model_config = ConfigDict(extra="forbid")


class BulkApplyParams(BaseModel):
    """Carga con los parámetros de una vista previa correcta y reciente (ADR-010)."""

    preview_run: str = Field(pattern=RUN_ID_PATTERN, description="Vista previa bulk_preview que se ejecuta.")
    confirm: str = Field(max_length=64, description="Alias de la conexión destino escrito a mano.")
    confirm_rows: int | None = Field(
        default=None, ge=0, description="Filas del destino afectadas (update/delete), escritas a mano."
    )
    accept_non_atomic: bool = Field(default=False, description="Acepta que la carga paralela no es atómica.")

    model_config = ConfigDict(extra="forbid")


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
    template_kind: str | None = None


@dataclass(frozen=True)
class OperationSpec:
    """Operación lanzable."""

    name: str
    title: str
    description: str
    model: type[BaseModel]
    #: ``False``: no sale en el formulario genérico (se lanza desde otra pantalla) y no se puede relanzar.
    form: bool = True

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
            elif prop.get("ubw_kind") == "template":
                kind = "template"
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
                    template_kind=prop.get("ubw_template_kind"),
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
    "migrate_plan": OperationSpec(
        name="migrate_plan",
        title="Plan de migración DDL",
        description="Traduce el DDL de un schema a otro motor con util_bbdd: script, avisos y visor. No escribe en "
        "ninguna base de datos.",
        model=MigratePlanParams,
    ),
    "migrate_apply": OperationSpec(
        name="migrate_apply",
        title="Aplicar migración DDL",
        description="Modo seco o aplicación de un plan de migración en una conexión destino.",
        model=MigrateApplyParams,
        form=False,
    ),
    "dump_preview": OperationSpec(
        name="dump_preview",
        title="Volcado de datos: vista previa",
        description="Modo seco de un volcado de filas entre dos conexiones: orden de carga por FK, ciclos, filas y "
        "avisos por tabla. No escribe; desde su detalle se lanza el volcado.",
        model=DumpPreviewParams,
    ),
    "dump_apply": OperationSpec(
        name="dump_apply",
        title="Volcado de datos",
        description="Copia las filas según una vista previa correcta y reciente.",
        model=DumpApplyParams,
        form=False,
    ),
    "dump_restore": OperationSpec(
        name="dump_restore",
        title="Restaurar constraints",
        description="Reactiva las constraints que un volcado interrumpido dejó desactivadas en el destino.",
        model=DumpRestoreParams,
        form=False,
    ),
    "bulk_preview": OperationSpec(
        name="bulk_preview",
        title="Carga bulk: vista previa",
        description="Valida un fichero contra una tabla, cuenta las filas afectadas y genera el SQL sin ejecutarlo.",
        model=BulkPreviewParams,
        form=False,
    ),
    "bulk_apply": OperationSpec(
        name="bulk_apply",
        title="Carga bulk",
        description="Inserta, actualiza o borra filas desde un fichero según una vista previa correcta y reciente.",
        model=BulkApplyParams,
        form=False,
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
