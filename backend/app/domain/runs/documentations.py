"""Documentación Markdown (util_bbdd 5.3.0): reglas de «Comparar con la documentación anterior».

``markdown_previous_run`` apunta a una documentación **del mismo proyecto**, terminada correctamente, con Markdown
(su ``catalog.json`` registrado y en disco), de la **misma conexión** (alias) y el **mismo schema**. Se comprueba al
encolar y otra vez en el worker, que copia ese ``catalog.json`` a ``inputs/previous/`` antes de generar: el run no
depende de la carpeta del otro ni de su retención.

El resultado, ``docs/changes.json``, es un ``SchemaDiff.to_dict()``: lo abre el visor de diferencias (``diff.py``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Project, Run
from app.domain.runs.errors import ArtifactNotFoundError, RunParamsError
from app.domain.runs.service import get_artifact_by_path

MARKDOWN_ROOT: Final = "outputs/markdown/documentacion/"
PREVIOUS_CATALOG: Final = MARKDOWN_ROOT + "docs/catalog.json"
CHANGES_PATH: Final = MARKDOWN_ROOT + "docs/changes.json"
_FIELD: Final = "markdown_previous_run"


def _error(message: str) -> RunParamsError:
    return RunParamsError(message, errors=[{"loc": ["body", "params", _FIELD], "msg": message, "type": "value_error"}])


def _schema(params: dict[str, Any]) -> str:
    return str(params.get("schema") or "").strip()


def previous_catalog(db: Session, project: Project, params: dict[str, Any], settings: Settings) -> Path | None:
    """``catalog.json`` de la documentación anterior elegida en ``params`` (``None`` si no se eligió).

    Raises:
        RunParamsError: No es del proyecto (sin revelar si existe), no es una documentación correcta, es de otra
            conexión u otro schema, o no tiene Markdown (o ya está purgada).
    """
    run_id = params.get(_FIELD)
    if not run_id:
        return None
    previous = db.get(Run, str(run_id))
    if previous is None or previous.project_id != project.id:
        raise _error("La documentación anterior no existe en el proyecto.")
    if previous.operation == "documentation" and previous.status == "purged":
        raise _error("La documentación anterior ya no está disponible: se purgó.")
    if previous.operation != "documentation" or previous.status != "succeeded":
        raise _error("La ejecución anterior debe ser una documentación terminada correctamente.")
    if previous.params.get("connection") != params.get("connection"):
        raise _error("La documentación anterior es de otra conexión.")
    if _schema(previous.params) != _schema(params):
        raise _error("La documentación anterior es de otro schema.")
    try:
        _, path = get_artifact_by_path(db, previous, PREVIOUS_CATALOG, settings)
    except ArtifactNotFoundError:
        raise _error("La documentación anterior no tiene Markdown o ya no está disponible.") from None
    return path


def check_launch(db: Session, project: Project, params: dict[str, Any], settings: Settings) -> None:
    """Al encolar una documentación: la documentación anterior, si se eligió, es válida (``previous_catalog``)."""
    previous_catalog(db, project, params, settings)
