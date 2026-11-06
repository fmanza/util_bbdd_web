"""Esquemas HTTP de las ejecuciones en administración (solo metadatos, sin ``params`` ni mensajes)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.api.v1.schemas_projects import RunStatus


class AdminRunOut(BaseModel):
    id: str
    project_id: int
    project_name: str
    operation: str
    status: RunStatus
    username: str | None
    created_at: datetime
    finished_at: datetime | None
    size_bytes: int
    artifacts_count: int


class AdminRunPage(BaseModel):
    items: list[AdminRunOut]
    total: int


class ProjectRunsSummaryOut(BaseModel):
    project_id: int
    project_name: str
    runs: int
    size_bytes: int


class ProjectRunsDelete(BaseModel):
    confirm: Annotated[str, Field(min_length=1, max_length=100, description="Nombre exacto del proyecto")]


class ProjectRunsDeleteOut(BaseModel):
    deleted: int
    skipped_active: int = Field(description="En cola o en curso: no se borran")
    skipped_pending_dump: int = Field(description="Volcados con constraints sin restaurar (G31): no se borran")
    freed_bytes: int
