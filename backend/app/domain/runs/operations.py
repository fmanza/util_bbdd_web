"""Catálogo de operaciones que se pueden lanzar como ejecución y sus parámetros.

Cada operación declara un modelo Pydantic (``extra="forbid"``) que valida los parámetros al encolar; los campos con
``ubw_kind="connection"`` son alias de una conexión del proyecto. La implementación vive en ``app/jobs/operations``.
Fase 3: solo ``noop`` (valida el motor de ejecuciones); las operaciones de util_bbdd llegan en las fases 4–9.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

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


@dataclass(frozen=True)
class OperationSpec:
    """Operación lanzable."""

    name: str
    title: str
    description: str
    model: type[BaseModel]

    @property
    def params(self) -> list[OperationParam]:
        schema = self.model.model_json_schema()
        required = set(schema.get("required", []))
        result = []
        for name, prop in schema.get("properties", {}).items():
            raw_type = prop.get("type") or next(
                (p.get("type") for p in prop.get("anyOf", []) if p.get("type") != "null"), "string"
            )
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
    return model.model_dump(mode="json")
