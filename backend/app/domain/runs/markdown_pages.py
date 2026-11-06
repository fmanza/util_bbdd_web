"""Índice de páginas de la documentación Markdown (util_bbdd 5.4.0, G51) para el árbol del visor.

util_bbdd escribe en ``manifest.json`` (``format_version`` 2) una entrada por página ``.md`` con su título en texto
plano, sección y papel. Aquí se lee con límites y se cruza con los artefactos registrados: solo salen páginas que la
ejecución tiene (``artifact_id``), así que el visor nunca construye una ruta con texto del manifiesto. Sin índice
(ejecuciones de util_bbdd 5.3.0) o si no es válido, ``source = "paths"`` y el visor deduce el árbol de las rutas.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Final, Literal

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Run
from app.domain.runs import service
from app.domain.runs.errors import ArtifactNotFoundError

logger = logging.getLogger(__name__)

ROOT: Final = "outputs/markdown/documentacion/"
DOCS: Final = f"{ROOT}docs/"
MANIFEST: Final = f"{ROOT}manifest.json"
MANIFEST_FORMAT: Final = "util_bbdd.doc.markdown"
#: Un manifiesto de 1 400 páginas pesa unos 300 KB; esto deja mucho margen sin leer ficheros enormes.
MAX_MANIFEST_BYTES: Final = 8 * 1024 * 1024
MAX_PAGES: Final = 100_000
MAX_TEXT: Final = 500
SECTIONS: Final = frozenset({"home", "tables", "views", "routines", "database", "traceability", "changes"})
ROLES: Final = frozenset({"home", "index", "letter", "object", "page"})

Role = Literal["home", "index", "letter", "object", "page"]


@dataclass(frozen=True)
class MarkdownPage:
    path: str
    title: str
    section: str
    role: Role
    artifact_id: int
    letter: str | None = None
    kind: str | None = None


@dataclass(frozen=True)
class MarkdownPages:
    source: Literal["manifest", "paths"]
    pages: list[MarkdownPage] = field(default_factory=list)


def _text(value: Any) -> str | None:
    return value[:MAX_TEXT] if isinstance(value, str) and value else None


def _entries(data: Any) -> list[Any] | None:
    """``pages`` de un manifiesto válido (formato y versión 2 o posterior), o ``None``."""
    if not isinstance(data, dict) or data.get("format") != MANIFEST_FORMAT:
        return None
    version = data.get("format_version")
    pages = data.get("pages")
    if not isinstance(version, int) or isinstance(version, bool) or version < 2 or not isinstance(pages, list):
        return None
    return pages[:MAX_PAGES]


def load_pages(db: Session, run: Run, settings: Settings) -> MarkdownPages:
    """Páginas de la documentación Markdown de ``run``.

    Raises:
        ArtifactNotFoundError: No es una documentación con Markdown o ya se purgó.
    """
    pages_by_path = {
        a.path[len(DOCS) :]: a for a in run.artifacts if a.path.startswith(DOCS) and a.path.endswith(".md")
    }
    if run.operation != "documentation" or not pages_by_path:
        raise ArtifactNotFoundError("Esta ejecución no tiene documentación Markdown.")
    manifest = next((a for a in run.artifacts if a.path == MANIFEST), None)
    if manifest is None or manifest.size_bytes > MAX_MANIFEST_BYTES:
        return MarkdownPages("paths")
    try:
        _, path = service.get_artifact_by_path(db, run, MANIFEST, settings)
        entries = _entries(json.loads(path.read_text(encoding="utf-8")))
    except (ArtifactNotFoundError, OSError, ValueError):
        logger.warning("manifest.json de la documentación ilegible", extra={"run_id": run.id})
        return MarkdownPages("paths")
    if entries is None:
        return MarkdownPages("paths")
    pages: list[MarkdownPage] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        relative, role, section = entry.get("path"), entry.get("role"), entry.get("section")
        artifact = pages_by_path.get(relative) if isinstance(relative, str) else None
        if artifact is None or role not in ROLES or section not in SECTIONS:
            continue  # solo páginas registradas y valores conocidos
        pages.append(
            MarkdownPage(
                path=str(relative),
                title=_text(entry.get("title")) or str(relative),
                section=str(section),
                role=role,
                artifact_id=artifact.id,
                letter=_text(entry.get("letter")) if role == "letter" else None,
                kind=_text(entry.get("kind")) if role == "object" else None,
            )
        )
    return MarkdownPages("manifest", pages) if pages else MarkdownPages("paths")
