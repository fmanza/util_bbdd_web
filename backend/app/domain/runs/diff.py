"""Diff de una ejecución ``compare`` (Fase 6): lectura del JSON guardado y evolución entre dos comparaciones.

El JSON (``outputs/diff/schema_diff.json``) lo escribe la capa de integración (``SchemaDiff.to_dict()`` desde la 1.2.0,
formato 1 propio antes) y lo lee ``read_diff``, que admite los dos. La evolución compara las **diferencias hoja** de dos comparaciones: cada una se identifica por su tipo, la
tabla, el objeto y el atributo, de modo que «la columna ``x.y`` difiere en el tipo» es la misma diferencia en las dos
fechas aunque cambien sus valores.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Run
from app.domain.runs.errors import ArtifactNotFoundError, DiffNotAvailableError, DiffTooLargeError
from app.domain.runs.service import get_artifact_by_path
from app.integrations.util_bbdd.compare import read_diff

logger = logging.getLogger(__name__)

DIFF_PATH: Final = "outputs/diff/schema_diff.json"
#: Tamaño máximo del JSON que se sirve al visor (los informes no tienen límite).
DIFF_MAX_BYTES: Final = 20 * 1024 * 1024


def load_diff(db: Session, run: Run, settings: Settings) -> dict[str, Any]:
    """Diff de una comparación terminada correctamente.

    Raises:
        DiffNotAvailableError: No es ``compare``, no terminó bien, está purgada o falta el fichero.
        DiffTooLargeError: El JSON supera ``DIFF_MAX_BYTES``.
    """
    if run.operation != "compare" or run.status != "succeeded":
        raise DiffNotAvailableError()
    try:
        artifact, path = get_artifact_by_path(db, run, DIFF_PATH, settings)
    except ArtifactNotFoundError:
        raise DiffNotAvailableError() from None
    if artifact.size_bytes > DIFF_MAX_BYTES:
        raise DiffTooLargeError()
    try:
        return read_diff(json.loads(path.read_text(encoding="utf-8")))
    except ValueError:  # JSON dañado o formato desconocido (json.JSONDecodeError también es ValueError)
        logger.warning("Diff guardado ilegible", extra={"run_id": run.id}, exc_info=True)
        raise DiffNotAvailableError() from None


@dataclass(frozen=True)
class DiffItem:
    """Una diferencia hoja con su clave estable."""

    kind: str
    table: str | None
    name: str
    attribute: str | None
    status: str
    source: str
    target: str

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.kind, (self.table or "").lower(), self.name.lower(), self.attribute or "")


def leaf_items(diff: dict[str, Any]) -> list[DiffItem]:
    """Diferencias hoja: tablas completas añadidas/eliminadas, y columnas, índices, FK y comentarios de las
    modificadas; vistas y rutinas."""
    items: list[DiffItem] = []
    for table in diff.get("table_diffs", []):
        name = table["table_name"]
        if table["status"] != "modified":
            items.append(DiffItem("table", None, name, None, table["status"], "", ""))
            continue
        for col in table.get("column_diffs", []):
            items.append(
                DiffItem(
                    "column",
                    name,
                    col["column_name"],
                    col["attribute"],
                    "modified",
                    col["source_value"],
                    col["target_value"],
                )
            )
        for index in table.get("index_diffs", []):
            items.append(
                DiffItem(
                    "index",
                    name,
                    index["index_name"],
                    None,
                    index["status"],
                    index["source_columns"],
                    index["target_columns"],
                )
            )
        for fk in table.get("fk_diffs", []):
            source = f"{fk['source_columns']} → {fk['source_referred_table']}" if fk["source_columns"] else ""
            target = f"{fk['target_columns']} → {fk['target_referred_table']}" if fk["target_columns"] else ""
            items.append(DiffItem("foreign_key", name, fk["fk_name"], None, fk["status"], source, target))
        for comment in table.get("comment_diffs", []):
            column = comment["column_name"]
            items.append(
                DiffItem(
                    "comment",
                    name,
                    column or name,
                    "column" if column else "table",
                    "modified",
                    comment["source_comment"],
                    comment["target_comment"],
                )
            )
    for view in diff.get("view_diffs", []):
        items.append(DiffItem("view", None, view["view_name"], None, view["status"], "", ""))
    for routine in diff.get("routine_diffs", []):
        items.append(
            DiffItem("routine", None, routine["routine_name"], routine["routine_type"], routine["status"], "", "")
        )
    return items


@dataclass(frozen=True)
class Evolution:
    """Diferencias nuevas, resueltas y persistentes de ``current`` respecto a ``baseline``."""

    new: list[DiffItem]
    resolved: list[DiffItem]
    persisting: list[DiffItem]
    labels_match: bool


def evolution(current: dict[str, Any], baseline: dict[str, Any]) -> Evolution:
    """Compara las diferencias hoja de dos diffs (``persisting`` lleva los valores de ``current``)."""
    now = {item.key: item for item in leaf_items(current)}
    before = {item.key: item for item in leaf_items(baseline)}
    return Evolution(
        new=[item for key, item in now.items() if key not in before],
        resolved=[item for key, item in before.items() if key not in now],
        persisting=[item for key, item in now.items() if key in before],
        labels_match=(
            current.get("source_label") == baseline.get("source_label")
            and current.get("target_label") == baseline.get("target_label")
        ),
    )
