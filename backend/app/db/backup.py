"""Copia de seguridad y restauración de ``config.db``, el workspace y los ficheros de conexión (Fase 10).

Una copia es una carpeta ``ubw-backup-<UTC>`` con:

- ``config.db``: instantánea consistente con la API ``backup`` de sqlite3 (vale en caliente, con WAL);
- ``workspace.tar.gz`` y ``files.tar.gz``: salidas de las ejecuciones y ficheros de ``UBW_FILES_DIR``;
- ``manifest.json``: versión de la aplicación, revisión de Alembic, tamaños y SHA-256 de cada fichero.

Las claves Fernet y la clave de sesión **no** se copian (son Docker secrets): sin ellas, las contraseñas de las
conexiones restauradas no se pueden descifrar. Se guardan aparte (``docs/guides/deployment.md``).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

from app import __version__
from app.core.config import Settings

MANIFEST: Final = "manifest.json"
FORMAT: Final = 1
_CHUNK: Final = 1024 * 1024


class BackupError(RuntimeError):
    """La copia no es válida o no se puede restaurar en este estado."""


@dataclass(frozen=True)
class BackupResult:
    folder: Path
    manifest: dict[str, object]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _config_db(settings: Settings) -> Path:
    return settings.data_dir / "config.db"


def alembic_revision(database: Path) -> str | None:
    """Revisión de Alembic de una ``config.db`` (``None`` si no tiene la tabla)."""
    with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as connection:
        try:
            row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        except sqlite3.OperationalError:
            return None
    return str(row[0]) if row else None


def _snapshot(source: Path, target: Path) -> None:
    src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def _tar(folder: Path, target: Path, *, exclude: Path | None = None) -> None:
    with tarfile.open(target, "w:gz") as archive:
        if folder.is_dir():
            for item in sorted(folder.iterdir()):
                if exclude is not None and item.resolve() == exclude.resolve():
                    continue
                archive.add(item, arcname=item.name)


def create_backup(settings: Settings, dest: Path, *, now: datetime | None = None) -> BackupResult:
    """Crea una copia en ``dest/ubw-backup-<UTC>`` y devuelve su carpeta y manifiesto.

    Raises:
        BackupError: No existe ``config.db``.
    """
    database = _config_db(settings)
    if not database.is_file():
        raise BackupError(f"No existe {database}.")
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    folder = dest / f"ubw-backup-{stamp}"
    folder.mkdir(parents=True, exist_ok=False)
    _snapshot(database, folder / "config.db")
    _tar(settings.workspace_dir, folder / "workspace.tar.gz")
    _tar(settings.files_dir, folder / "files.tar.gz", exclude=dest)
    files = {
        name: {"size": (folder / name).stat().st_size, "sha256": _sha256(folder / name)}
        for name in ("config.db", "workspace.tar.gz", "files.tar.gz")
    }
    manifest: dict[str, object] = {
        "format": FORMAT,
        "app_version": __version__,
        "alembic_revision": alembic_revision(folder / "config.db"),
        "created_at": (now or datetime.now(UTC)).isoformat(),
        "files": files,
    }
    (folder / MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return BackupResult(folder, manifest)


def verify_backup(folder: Path) -> dict[str, object]:
    """Lee el manifiesto y comprueba tamaño y SHA-256 de cada fichero.

    Raises:
        BackupError: Falta el manifiesto o algún fichero, o no coincide.
    """
    try:
        manifest = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BackupError(f"{folder} no es una copia válida (sin {MANIFEST}).") from exc
    if manifest.get("format") != FORMAT:
        raise BackupError(f"Formato de copia no soportado: {manifest.get('format')}.")
    for name, info in dict(manifest.get("files", {})).items():
        path = folder / name
        if not path.is_file() or path.stat().st_size != info["size"] or _sha256(path) != info["sha256"]:
            raise BackupError(f"{name} falta o está dañado (no coincide con el manifiesto).")
    return dict(manifest)


def worker_recently_alive(settings: Settings, *, within: timedelta = timedelta(seconds=60)) -> bool:
    """``True`` si algún worker ha latido hace poco: la aplicación sigue en marcha."""
    from sqlalchemy import create_engine, func, select
    from sqlalchemy.exc import SQLAlchemyError

    from app.db.models import Worker

    if not _config_db(settings).is_file():
        return False
    engine = create_engine(settings.database_url)
    try:
        with engine.connect() as connection:
            last = connection.execute(select(func.max(Worker.heartbeat_at))).scalar()
    except SQLAlchemyError:
        return False
    finally:
        engine.dispose()
    return last is not None and last >= datetime.now(UTC) - within


def _safe_extract(archive: Path, target: Path) -> None:
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(target, filter="data")  # sin rutas absolutas, `..`, enlaces fuera ni ficheros especiales


def _replace_contents(folder: Path, staged: Path) -> None:
    """Vacía ``folder`` (puede ser la raíz de un volumen: no se renombra) y mueve dentro lo de ``staged``."""
    folder.mkdir(parents=True, exist_ok=True)
    for item in folder.iterdir():
        if item.is_dir() and not item.is_symlink():
            shutil.rmtree(item)
        else:
            item.unlink()
    for item in staged.iterdir():
        shutil.move(str(item), folder / item.name)


def restore_backup(settings: Settings, folder: Path, *, now: datetime | None = None) -> Path:
    """Restaura una copia verificada sobre ``config.db``, el workspace y ``UBW_FILES_DIR``.

    Primero extrae y valida los ``tar`` en una carpeta temporal: si alguno no es válido no se toca nada. Guarda la
    ``config.db`` actual como ``config.db.pre-restore-<UTC>`` (el workspace actual se sustituye). Debe ejecutarse con
    la API y el worker parados.

    Returns:
        Ruta de la copia previa de ``config.db`` (o la que tendría si no existía ninguna).

    Raises:
        BackupError: Copia no válida o dentro de una carpeta que se sustituye.
        tarfile.FilterError: Un ``tar`` intenta escribir fuera de su carpeta.
    """
    source = folder.resolve()
    for replaced in (settings.workspace_dir, settings.files_dir):
        if source.is_relative_to(replaced.resolve()):
            raise BackupError(f"La copia no puede estar dentro de {replaced}: se vacía al restaurar.")
    verify_backup(folder)
    database = _config_db(settings)
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    staging = settings.data_dir / f".restore-{stamp}"
    try:
        for name in ("workspace", "files"):
            (staging / name).mkdir(parents=True)
            _safe_extract(folder / f"{name}.tar.gz", staging / name)
        previous = database.with_name(f"config.db.pre-restore-{stamp}")
        if database.is_file():
            _snapshot(database, previous)
        for suffix in ("-wal", "-shm"):
            database.with_name(database.name + suffix).unlink(missing_ok=True)
        shutil.copyfile(folder / "config.db", database)
        _replace_contents(settings.workspace_dir, staging / "workspace")
        _replace_contents(settings.files_dir, staging / "files")
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return previous
