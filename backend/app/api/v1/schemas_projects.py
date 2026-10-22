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
    type: Literal["string", "integer", "float", "boolean", "connection"]
    required: bool
    default: Any = None
    description: str
    minimum: float | None
    maximum: float | None
    options: list[str] | None = Field(default=None, description="Valores permitidos (desplegable)")
    group: str | None = Field(default=None, description="Sección del formulario")


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


class RunPage(BaseModel):
    items: list[RunOut]
    total: int
