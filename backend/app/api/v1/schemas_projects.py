"""Esquemas HTTP de proyectos, miembros, conexiones del proyecto, operaciones, ejecuciones y artefactos."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.runs.operations import ALIAS_PATTERN

ProjectRole = Literal["owner", "editor", "viewer"]
RunStatus = Literal["queued", "running", "succeeded", "failed", "cancelled", "purged"]
ProjectName = Annotated[str, Field(min_length=1, max_length=100)]
Description = Annotated[str, Field(max_length=500)]
Alias = Annotated[str, Field(pattern=ALIAS_PATTERN, description="Minúsculas, números, guion y guion bajo (1-32)")]


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- proyectos ---------------------------------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    name: ProjectName
    description: Description = ""


class ProjectUpdate(BaseModel):
    name: ProjectName | None = None
    description: Description | None = None


class ProjectOut(BaseModel):
    """Proyecto con el rol del usuario actual."""

    id: int
    name: str
    description: str
    owner_id: int
    my_role: ProjectRole
    created_at: datetime
    updated_at: datetime


class ProjectPage(BaseModel):
    items: list[ProjectOut]
    total: int


class MemberCreate(BaseModel):
    username: Annotated[str, Field(min_length=1, max_length=64)]
    role: ProjectRole = "viewer"


class MemberUpdate(BaseModel):
    role: ProjectRole


class MemberOut(BaseModel):
    user_id: int
    username: str
    display_name: str
    role: ProjectRole
    added_at: datetime


class ProjectConnectionCreate(BaseModel):
    connection_id: int
    alias: Alias


class ProjectConnectionOut(BaseModel):
    """Conexión del proyecto: alias, motor y nombre (nunca el secreto ni los parámetros)."""

    id: int
    alias: str
    connection_id: int
    connection_name: str
    db_type: str
    read_only: bool
    created_at: datetime


# --- operaciones -------------------------------------------------------------------------------------------------


class OperationParamOut(_Out):
    name: str
    type: Literal["string", "integer", "float", "boolean", "connection", "template", "run"]
    required: bool
    default: Any = None
    description: str
    minimum: float | None
    maximum: float | None
    options: list[str] | None = Field(default=None, description="Valores permitidos (desplegable)")
    group: str | None = Field(default=None, description="Sección del formulario")
    template_kind: Literal["word", "excel", "trace"] | None = Field(
        default=None, description="Con ``type=template``: tipo de plantilla de documento que se elige"
    )
    run_operation: str | None = Field(
        default=None, description="Con ``type=run``: operación de las ejecuciones anteriores del proyecto que se eligen"
    )
    requires: str | None = Field(
        default=None, description="Solo se muestra (y se envía) si este parámetro booleano está activado"
    )


class OperationOut(BaseModel):
    name: str
    title: str
    description: str
    params: list[OperationParamOut]
    form: bool = Field(default=True, description="Sale en el formulario genérico de lanzamiento")


# --- ejecuciones -------------------------------------------------------------------------------------------------


class RunCreate(BaseModel):
    operation: Annotated[str, Field(min_length=1, max_length=32)]
    params: dict[str, Any] = Field(default_factory=dict)


class ArtifactOut(_Out):
    id: int
    path: str
    kind: str
    mime: str
    size_bytes: int
    sha256: str
    created_at: datetime
    previewable: bool = False


class RunOut(BaseModel):
    """Ejecución (una fila por ejecución en el historial)."""

    id: str
    project_id: int
    project_name: str
    operation: str
    params: dict[str, Any]
    status: RunStatus
    phase: str | None
    progress_message: str | None
    progress_pct: int | None
    error_code: str | None
    error_message: str | None
    cancel_requested: bool
    user_id: int | None
    username: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_seconds: float | None
    size_bytes: int
    artifacts_count: int
    relaunched_from: str | None


class RunDetailOut(RunOut):
    """Ejecución con sus artefactos y el rol del usuario en el proyecto."""

    my_role: ProjectRole
    artifacts: list[ArtifactOut]
    site_url: str | None = Field(
        default=None, description="URL firmada y temporal del sitio HTML generado (para el iframe con origen opaco)"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Avisos de la ejecución (p. ej. una plantilla que no se pudo aplicar)"
    )
    warnings_by_format: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Avisos de la documentación por formato (``word``, ``excel``, ``markdown``), también incluidos en "
        "``warnings``; vacío en ejecuciones anteriores a la 1.12.0",
    )
    templates_applied: dict[str, bool] = Field(
        default_factory=dict,
        description="Plantillas de la documentación por tipo (``word``, ``excel``, ``trace``): si se aplicó la elegida",
    )
    has_diff: bool = Field(
        default=False,
        description="Tiene diff de esquemas para el visor (``GET /runs/{id}/diff``): una comparación o una documentación "
        "Markdown comparada con otra anterior",
    )


class MarkdownPageOut(_Out):
    """Página de la documentación Markdown (índice de util_bbdd 5.4.0, G51). ``title`` viene de la BD documentada."""

    path: str = Field(description="Ruta relativa a ``docs/``")
    title: str = Field(description="Título en texto plano (escápalo al pintarlo)")
    section: str = Field(
        description="``home``, ``tables``, ``views``, ``routines``, ``database``, ``traceability`` o ``changes``"
    )
    role: Literal["home", "index", "letter", "object", "page"]
    letter: str | None = Field(default=None, description="Solo en ``letter``")
    kind: str | None = Field(default=None, description="Solo en ``object``: tipo del catálogo")
    artifact_id: int = Field(description="Artefacto de la página (vista previa y descarga)")


class MarkdownPagesOut(BaseModel):
    """Árbol de la documentación Markdown: del índice de ``manifest.json`` o, sin él, ``paths`` (el visor lo deduce de
    las rutas de los artefactos)."""

    source: Literal["manifest", "paths"]
    pages: list[MarkdownPageOut]


class RunPage(BaseModel):
    items: list[RunOut]
    total: int
