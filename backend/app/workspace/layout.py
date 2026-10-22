"""Estructura del workspace por ejecución (ADR-005), rutas seguras, artefactos y ZIP en *streaming*.

```text
{workspace}/users/{owner_id}/projects/{project_id}/runs/{YYYYMMDD-HHMMSS}_{operation}_{run_id}/
  run.json   logs/run.log   outputs/{word,excel,html,sql,markdown,graphs}/   inputs/
```

Solo se construyen rutas con IDs y valores validados (``operation`` es un nombre del registro); antes de servir un
fichero se comprueba con ``resolve()`` + ``is_relative_to`` que no sale de la carpeta del run.
"""

from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import os
import re
import shutil
import tempfile
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Final

MANIFEST: Final = "run.json"
RUN_LOG: Final = "logs/run.log"
OUTPUT_KINDS: Final = ("word", "excel", "html", "sql", "markdown", "graphs", "diff", "plan", "audit")
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_-]+$")
_CHUNK = 64 * 1024

_MIME_OVERRIDES: Final[dict[str, str]] = {
    ".md": "text/markdown",
    ".sql": "application/sql",
    ".log": "text/plain",
    ".json": "application/json",
    ".jsonl": "application/x-ndjson",
    ".svg": "image/svg+xml",
    ".html": "text/html",
    ".js": "text/javascript",
    ".css": "text/css",
    ".png": "image/png",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class UnsafePathError(ValueError):
    """La ruta pedida sale de la carpeta permitida."""


@dataclass(frozen=True)
class ArtifactFile:
    """Fichero de una ejecución, con la ruta relativa a la carpeta del run en formato POSIX."""

    path: str
    kind: str
    mime: str
    size_bytes: int
    sha256: str


def run_relative_path(owner_id: int, project_id: int, created_at: datetime, operation: str, run_id: str) -> str:
    """Ruta del run relativa a la raíz del workspace (solo IDs y la operación validada)."""
    if not _SAFE_SEGMENT.fullmatch(operation) or not _SAFE_SEGMENT.fullmatch(run_id):
        raise UnsafePathError("Operación o identificador de ejecución no válidos")
    name = f"{created_at:%Y%m%d-%H%M%S}_{operation}_{run_id}"
    return f"users/{int(owner_id)}/projects/{int(project_id)}/runs/{name}"


def safe_path(root: Path, relative: str) -> Path:
    """``root / relative`` resuelto, o error si sale de ``root`` (``..``, rutas absolutas, enlaces).

    Raises:
        UnsafePathError: La ruta no queda dentro de ``root``.
    """
    base = root.resolve()
    # Las rutas del workspace son siempre POSIX relativas: se rechazan también ``\`` y letras de unidad para que el
    # resultado no dependa del sistema operativo.
    if (
        not relative
        or "\x00" in relative
        or "\\" in relative
        or PureWindowsPath(relative).drive
        or PurePosixPath(relative).is_absolute()
        or Path(relative).is_absolute()
    ):
        raise UnsafePathError(relative)
    candidate = (base / relative).resolve()
    if candidate == base or not candidate.is_relative_to(base):
        raise UnsafePathError(relative)
    return candidate


def run_dir(workspace_dir: Path, relative: str) -> Path:
    """Carpeta absoluta de un run a partir de ``runs.workspace_path``."""
    return safe_path(workspace_dir, relative)


def ensure_layout(directory: Path) -> None:
    """Crea ``logs/``, ``inputs/`` y ``outputs/<formato>/``."""
    (directory / "logs").mkdir(parents=True, exist_ok=True)
    (directory / "inputs").mkdir(exist_ok=True)
    for kind in OUTPUT_KINDS:
        (directory / "outputs" / kind).mkdir(parents=True, exist_ok=True)


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    """Escribe JSON en un temporal y lo renombra (nunca queda un ``run.json`` a medias)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _kind(relative: PurePosixPath) -> str:
    if relative.as_posix() == MANIFEST:
        return "manifest"
    if relative.as_posix() == RUN_LOG:
        return "log"
    parts = relative.parts
    if len(parts) >= 3 and parts[0] == "outputs" and parts[1] in OUTPUT_KINDS:
        return parts[1]
    return "other"


def mime_type(name: str) -> str:
    suffix = PurePosixPath(name).suffix.lower()
    return _MIME_OVERRIDES.get(suffix) or mimetypes.guess_type(name)[0] or "application/octet-stream"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_artifacts(directory: Path) -> list[ArtifactFile]:
    """Ficheros del run (``run.json``, ``logs/run.log`` y ``outputs/**``), sin enlaces simbólicos ni temporales."""
    files: list[ArtifactFile] = []
    base = directory.resolve()
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.is_symlink() or path.name.startswith(".tmp-"):
            continue
        relative = PurePosixPath(path.relative_to(base).as_posix())
        if relative.parts[0] not in ("outputs", "logs") and relative.as_posix() != MANIFEST:
            continue
        files.append(
            ArtifactFile(
                path=relative.as_posix(),
                kind=_kind(relative),
                mime=mime_type(relative.name),
                size_bytes=path.stat().st_size,
                sha256=_sha256(path),
            )
        )
    return files


def directory_size(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(p.stat().st_size for p in directory.rglob("*") if p.is_file() and not p.is_symlink())


def remove_tree(directory: Path) -> None:
    """Borra la carpeta de un run (si existe)."""
    shutil.rmtree(directory, ignore_errors=True)


class _Drain(io.RawIOBase):
    """Destino de escritura no posicionable que acumula lo escrito hasta que se vacía."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def writable(self) -> bool:
        return True

    def write(self, data: Any) -> int:
        self._buffer.extend(data)
        return len(data)

    def drain(self) -> bytes:
        chunk = bytes(self._buffer)
        self._buffer.clear()
        return chunk


def zip_stream(directory: Path, relatives: list[str], *, prefix: str) -> Iterator[bytes]:
    """ZIP de ``relatives`` (rutas relativas a ``directory``) generado por trozos, sin fichero temporal."""
    sink = _Drain()
    with zipfile.ZipFile(sink, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in relatives:
            path = safe_path(directory, relative)
            if not path.is_file():
                continue
            with path.open("rb") as source, archive.open(f"{prefix}/{relative}", "w", force_zip64=True) as target:
                for chunk in iter(lambda: source.read(_CHUNK), b""):
                    target.write(chunk)
                    if data := sink.drain():
                        yield data
            if data := sink.drain():
                yield data
    if data := sink.drain():
        yield data
