"""Esquemas de las plantillas de documento (ADR-011)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

TemplateKind = Literal["word", "excel"]


class TemplateOut(BaseModel):
    """Plantilla Word o Excel (sin la ruta en el servidor)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    scope: Literal["global", "project"]
    kind: TemplateKind
    name: str
    filename: str
    size_bytes: int
    sha256: str
    table_style: str | None = Field(description="Estilo de tabla que se aplica a la documentación")
    table_styles: list[str] = Field(description="Estilos de tabla que se pueden elegir")
    username: str | None = None
    created_at: datetime
    updated_at: datetime


class TemplateUpdate(BaseModel):
    """Cambio de nombre o de estilo de tabla (uno de ``table_styles``); un campo que no se envía no cambia."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str | None, Field(min_length=1, max_length=100)] = None
    table_style: Annotated[str | None, Field(min_length=1, max_length=100)] = Field(
        default=None, description="Estilo de tabla; ``null`` explícito vuelve al estilo por defecto"
    )

    @property
    def default_table_style(self) -> bool:
        """Se envió ``table_style: null``: quitar el estilo elegido."""
        return "table_style" in self.model_fields_set and self.table_style is None
