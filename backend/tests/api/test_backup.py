"""Fase 10: copia de seguridad y restauración (``python -m app.cli backup|verify-backup|restore``)."""

from __future__ import annotations

import json
import sqlite3
import tarfile
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cli import main
from app.core.config import Settings
from app.db.backup import BackupError, create_backup, restore_backup, verify_backup
from app.db.models import User, Worker, utcnow
from app.db.session import get_engine


def _seed(settings: Settings) -> None:
    run = settings.workspace_dir / "users" / "1" / "runs" / "R1"
    run.mkdir(parents=True)
    (run / "run.json").write_text('{"ok": true}', encoding="utf-8")
    (settings.files_dir / "ventas.db").write_bytes(b"SQLite format 3\x00datos")


def _release(db: Session) -> None:
    """Cierra las conexiones (con la aplicación parada no hay; en Windows bloquearían ``config.db-wal``)."""
    db.close()
    get_engine().dispose()


def test_backup_and_restore_round_trip(db: Session, migrated: Settings, user: User, tmp_path: Path) -> None:
    _seed(migrated)
    result = create_backup(migrated, tmp_path / "copias")
    manifest = verify_backup(result.folder)
    assert manifest["alembic_revision"] == "0008"
    assert set(dict(manifest["files"])) == {"config.db", "workspace.tar.gz", "files.tar.gz"}

    # Cambios posteriores a la copia: se pierden al restaurar.
    user.display_name = "Cambiado"
    db.commit()
    (migrated.workspace_dir / "nuevo.txt").write_text("x", encoding="utf-8")
    (migrated.files_dir / "ventas.db").write_bytes(b"otra")
    _release(db)

    previous = restore_backup(migrated, result.folder)

    assert previous.is_file()
    with sqlite3.connect(migrated.data_dir / "config.db") as connection:
        assert connection.execute("SELECT display_name FROM users WHERE username='ana'").fetchone() == ("Ana",)
    with sqlite3.connect(previous) as connection:
        assert connection.execute("SELECT display_name FROM users WHERE username='ana'").fetchone() == ("Cambiado",)
    assert not (migrated.workspace_dir / "nuevo.txt").exists()
    assert (migrated.workspace_dir / "users" / "1" / "runs" / "R1" / "run.json").is_file()
    assert (migrated.files_dir / "ventas.db").read_bytes() == b"SQLite format 3\x00datos"


def test_hot_backup_is_consistent_with_pending_wal(db: Session, migrated: Settings, user: User, tmp_path: Path) -> None:
    """Con escrituras en el WAL sin *checkpoint*, la instantánea las incluye."""
    user.display_name = "En el WAL"
    db.commit()
    result = create_backup(migrated, tmp_path)
    with sqlite3.connect(result.folder / "config.db") as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("SELECT display_name FROM users WHERE username='ana'").fetchone() == ("En el WAL",)


def test_damaged_backup_is_rejected(migrated: Settings, tmp_path: Path) -> None:
    result = create_backup(migrated, tmp_path)
    with (result.folder / "workspace.tar.gz").open("ab") as handle:
        handle.write(b"x")
    with pytest.raises(BackupError, match="dañado"):
        verify_backup(result.folder)
    with pytest.raises(BackupError, match="no es una copia"):
        verify_backup(tmp_path)


def test_restore_rejects_paths_outside_the_target(migrated: Settings, tmp_path: Path) -> None:
    """Un ``tar`` con ``..`` no escribe fuera del workspace (filtro ``data``) y no se sustituye nada."""
    result = create_backup(migrated, tmp_path / "copias")
    evil = tmp_path / "evil.tar.gz"
    payload = tmp_path / "payload.txt"
    payload.write_text("x", encoding="utf-8")
    with tarfile.open(evil, "w:gz") as archive:
        archive.add(payload, arcname="../fuera.txt")
    target = result.folder / "workspace.tar.gz"
    target.write_bytes(evil.read_bytes())
    manifest = json.loads((result.folder / "manifest.json").read_text(encoding="utf-8"))
    import hashlib

    manifest["files"]["workspace.tar.gz"] = {
        "size": target.stat().st_size,
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    }
    (result.folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    get_engine().dispose()
    with pytest.raises(tarfile.OutsideDestinationError):
        restore_backup(migrated, result.folder)
    assert not (migrated.workspace_dir.parent / "fuera.txt").exists()
    assert not list(migrated.data_dir.glob("config.db.pre-restore-*"))
    assert not list(migrated.data_dir.glob(".restore-*"))


def test_restore_refuses_a_backup_inside_the_replaced_folders(migrated: Settings) -> None:
    result = create_backup(migrated, migrated.files_dir / "copias")
    with pytest.raises(BackupError, match="dentro de"):
        restore_backup(migrated, result.folder)


def test_cli_backup_verify_and_restore(
    db: Session, migrated: Settings, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["backup", "--dest", str(tmp_path)]) == 0
    folder = next(tmp_path.glob("ubw-backup-*"))
    assert "no van en la copia" in capsys.readouterr().out
    assert main(["verify-backup", "--from", str(folder)]) == 0

    assert main(["restore", "--from", str(folder)]) == 2  # sin --force
    db.add(Worker(id="w1", hostname="h", pid=1, heartbeat_at=utcnow()))
    db.commit()
    assert main(["restore", "--from", str(folder), "--force"]) == 1
    assert "worker en marcha" in capsys.readouterr().err

    db.execute(Worker.__table__.delete())
    db.commit()
    assert db.scalars(select(Worker)).first() is None
    _release(db)
    assert main(["restore", "--from", str(folder), "--force"]) == 0


def test_cli_restore_refuses_a_newer_revision(migrated: Settings, tmp_path: Path) -> None:
    result = create_backup(migrated, tmp_path)
    with sqlite3.connect(result.folder / "config.db") as connection:
        connection.execute("UPDATE alembic_version SET version_num = '9999'")
    import hashlib

    manifest = json.loads((result.folder / "manifest.json").read_text(encoding="utf-8"))
    manifest["alembic_revision"] = "9999"
    data = (result.folder / "config.db").read_bytes()
    manifest["files"]["config.db"] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    (result.folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert main(["restore", "--from", str(result.folder), "--force"]) == 1
