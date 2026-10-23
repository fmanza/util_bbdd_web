"""Comandos de administración.

Uso::

    python -m app.cli create-admin --username admin [--display-name "Administración"] [--password-stdin]
    python -m app.cli rotate-secrets
    python -m app.cli backup [--dest /data/backups]
    python -m app.cli verify-backup --from /data/backups/ubw-backup-<UTC>
    python -m app.cli restore --from /data/backups/ubw-backup-<UTC> --force

Sin ``--password-stdin`` la contraseña se pide dos veces por terminal (``getpass``). En Docker::

    docker compose exec web python -m app.cli create-admin --username admin
"""

from __future__ import annotations

import argparse
import getpass
import logging
import sys
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.db.session import get_engine
from app.domain.identity.audit import CLI_CONTEXT
from app.domain.identity.users import create_user

logger = logging.getLogger(__name__)


def _read_password(from_stdin: bool) -> str:
    if from_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    first = getpass.getpass("Contraseña: ")
    if getpass.getpass("Repite la contraseña: ") != first:
        raise SystemExit("Las contraseñas no coinciden.")
    return first


def create_admin(username: str, display_name: str | None, *, password_stdin: bool) -> int:
    """Crea un usuario ``admin``; devuelve el código de salida."""
    settings = get_settings()
    password = _read_password(password_stdin)
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as db:
        try:
            user = create_user(
                db,
                username=username,
                display_name=display_name or username,
                password=password,
                role="admin",
                settings=settings,
                ctx=CLI_CONTEXT,
                actor_id=None,
            )
        except AppError as exc:
            print(f"Error: {exc.title}. {exc.detail or ''}".strip(), file=sys.stderr)
            return 1
    print(f"Administrador «{user.username}» creado (id {user.id}).")
    return 0


def rotate_secrets() -> int:
    """Re-cifra los secretos de conexión con la primera clave de ``UBW_FERNET_KEYS``; devuelve el código de salida."""
    from app.domain.connections.crypto import SecretDecryptError
    from app.domain.connections.service import rotate_secrets as rotate

    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as db:
        try:
            count = rotate(db, get_settings())
        except SecretDecryptError:
            db.rollback()
            print(
                "Error: algún secreto no se descifra con las claves configuradas; no se ha cambiado nada.",
                file=sys.stderr,
            )
            return 1
    print(f"Secretos re-cifrados con la clave principal: {count}. Ya puedes retirar la clave antigua.")
    return 0


def backup(dest: Path | None) -> int:
    """Copia ``config.db`` (en caliente), el workspace y ``UBW_FILES_DIR``; devuelve el código de salida."""
    from app.db.backup import BackupError, create_backup

    settings = get_settings()
    try:
        result = create_backup(settings, dest or settings.data_dir / "backups")
    except (BackupError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Copia creada en {result.folder} (revisión {result.manifest['alembic_revision']}).")
    print("Recuerda: las claves (secrets/*.txt) no van en la copia; guárdalas aparte.")
    return 0


def verify_backup(source: Path) -> int:
    from app.db.backup import BackupError
    from app.db.backup import verify_backup as verify

    try:
        manifest = verify(source)
    except BackupError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Copia correcta: versión {manifest['app_version']}, revisión {manifest['alembic_revision']}.")
    return 0


def restore(source: Path, *, force: bool) -> int:
    """Restaura una copia con la aplicación parada (``docker compose run --rm --no-deps web …``)."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from app.db.backup import BackupError, restore_backup, worker_recently_alive
    from app.db.backup import verify_backup as verify

    settings = get_settings()
    if not force:
        print("Error: restaurar sustituye config.db, el workspace y los ficheros; repite con --force.", file=sys.stderr)
        return 2
    if worker_recently_alive(settings):
        print("Error: hay un worker en marcha; para la aplicación (docker compose stop) y repite.", file=sys.stderr)
        return 1
    try:
        manifest = verify(source)
        backend = Path(__file__).resolve().parents[1]
        config = Config(str(backend / "alembic.ini"))
        config.set_main_option("script_location", str(backend / "alembic"))
        scripts = ScriptDirectory.from_config(config)
        revision = manifest.get("alembic_revision")
        if revision is not None and revision not in {script.revision for script in scripts.walk_revisions()}:
            raise BackupError(f"La copia es de una versión más nueva (revisión {revision}): actualiza antes.")
        previous = restore_backup(settings, source)
    except (BackupError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Copia restaurada (versión {manifest['app_version']}). La config.db anterior está en {previous}.")
    print("Al arrancar, la aplicación aplica las migraciones pendientes.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Administración de util_bbdd_web")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-admin", help="crea un usuario administrador")
    admin.add_argument("--username", required=True)
    admin.add_argument("--display-name")
    admin.add_argument("--password-stdin", action="store_true", help="lee la contraseña de la entrada estándar")
    commands.add_parser("rotate-secrets", help="re-cifra los secretos de conexión con la clave Fernet principal")
    backup_cmd = commands.add_parser("backup", help="copia config.db, el workspace y los ficheros de conexión")
    backup_cmd.add_argument("--dest", type=Path, help="carpeta destino (por defecto, <UBW_DATA_DIR>/backups)")
    verify_cmd = commands.add_parser("verify-backup", help="comprueba una copia contra su manifiesto")
    verify_cmd.add_argument("--from", dest="source", type=Path, required=True)
    restore_cmd = commands.add_parser("restore", help="restaura una copia (con la aplicación parada)")
    restore_cmd.add_argument("--from", dest="source", type=Path, required=True)
    restore_cmd.add_argument("--force", action="store_true", help="confirma que se sustituyen los datos actuales")
    args = parser.parse_args(argv)

    configure_logging(get_settings().log_level)
    if args.command == "create-admin":
        return create_admin(args.username, args.display_name, password_stdin=args.password_stdin)
    if args.command == "rotate-secrets":
        return rotate_secrets()
    if args.command == "backup":
        return backup(args.dest)
    if args.command == "verify-backup":
        return verify_backup(args.source)
    if args.command == "restore":
        return restore(args.source, force=args.force)
    return 2  # pragma: no cover - argparse exige un comando


if __name__ == "__main__":
    raise SystemExit(main())
