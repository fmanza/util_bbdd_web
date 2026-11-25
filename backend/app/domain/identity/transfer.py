"""Transferencia a otro usuario de lo que impide borrar uno (ADR-013, enmienda de la entrega B).

Se transfiere, todo o nada:

- los proyectos que creó: cambia ``projects.owner_id``, su carpeta ``users/<origen>/projects/<id>`` se mueve a
  ``users/<destino>/projects/<id>`` y se reescribe el prefijo de ``runs.workspace_path``, ``uploads.path`` y
  ``document_templates.path`` (las rutas de los artefactos son relativas al run y no cambian);
- la propiedad de los proyectos de los que es ``owner``: el destino pasa a ``owner`` (o sube a ``owner``);
- sus conexiones compartidas o asociadas a proyectos (las privadas sin uso no se ceden: se borran con la cuenta).

Base de datos y disco no se confirman a la vez: antes de mover se escribe un diario en ``.transfers/<id>.json`` y,
si el proceso muere entre mover y confirmar, el worker lo resuelve al arrancar (:func:`recover_transfers`).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Literal

from sqlalchemy import delete, func, literal, select, update
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.core.config import Settings
from app.core.ulid import new_ulid
from app.db.models import (
    Connection,
    DocumentTemplate,
    Project,
    ProjectConnection,
    ProjectMember,
    Run,
    Upload,
    User,
    utcnow,
)
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.identity.errors import TransferBlockedError
from app.workspace.layout import project_prefix, safe_path

logger = logging.getLogger(__name__)

#: Carpeta de los diarios de transferencia dentro del workspace.
JOURNAL_DIR: Final = ".transfers"
#: Longitud máxima de los nombres de proyectos y conexiones (``String(100)``).
_NAME_MAX: Final = 100

TransferReason = Literal["same_user", "target_inactive", "target_cannot_share", "busy"]


@dataclass(frozen=True)
class Item:
    """Proyecto o conexión afectados; ``new_name`` si choca con uno del destino y se renombra."""

    id: int
    name: str
    new_name: str | None = None
    role: str | None = None
    visibility: str | None = None


@dataclass(frozen=True)
class TransferPlan:
    """Lo que haría (o hizo) la transferencia y lo que la impide."""

    reasons: list[TransferReason] = field(default_factory=list)
    created_projects: list[Item] = field(default_factory=list)
    owned_projects: list[Item] = field(default_factory=list)
    other_memberships: list[Item] = field(default_factory=list)
    connections: list[Item] = field(default_factory=list)
    busy_projects: list[Item] = field(default_factory=list)

    @property
    def can_transfer(self) -> bool:
        return not self.reasons

    def as_extra(self) -> dict[str, object]:
        """Campos adicionales del *problem details* del ``409`` (y de la respuesta)."""

        def items(values: list[Item]) -> list[dict[str, object]]:
            return [{k: v for k, v in vars(i).items() if k in ("id", "name") or v is not None} for i in values]

        return {
            "reasons": list(self.reasons),
            "created_projects": items(self.created_projects),
            "owned_projects": items(self.owned_projects),
            "other_memberships": items(self.other_memberships),
            "connections": items(self.connections),
            "busy_projects": items(self.busy_projects),
        }


def _free_name(name: str, suffix: str, taken: set[str]) -> str:
    """``name`` + ``suffix`` (y `` 2``, `` 3``… si hace falta) que no esté en ``taken``, recortado a 100."""
    n = 1
    while True:
        tail = suffix if n == 1 else f"{suffix} {n}"
        candidate = name[: _NAME_MAX - len(tail)].rstrip() + tail
        if candidate.lower() not in taken:
            taken.add(candidate.lower())
            return candidate
        n += 1


def _renamed(rows: list[tuple[int, str]], target_names: set[str], suffix: str) -> list[tuple[int, str, str | None]]:
    """Nombres finales: los que chocan con uno del destino llevan ``suffix``; nunca chocan entre sí."""
    taken = target_names | {name.lower() for _, name in rows}
    out: list[tuple[int, str, str | None]] = []
    for item_id, name in rows:
        new = _free_name(name, suffix, taken) if name.lower() in target_names else None
        out.append((item_id, name, new))
    return out


def transfer_preview(db: Session, origin: User, target: User) -> TransferPlan:
    """Qué movería transferir lo de ``origin`` a ``target`` y qué lo impide."""
    reasons: list[TransferReason] = []
    if origin.id == target.id:
        reasons.append("same_user")
    if not target.is_active:
        reasons.append("target_inactive")
    suffix = f" (de {origin.username})"
    same = origin.id == target.id  # bloqueado: sin renombrados que no tendrían sentido

    created_rows = [
        (pid, name)
        for pid, name in db.execute(
            select(Project.id, Project.name)
            .where(Project.owner_id == origin.id)
            .order_by(func.lower(Project.name), Project.id)
        ).all()
    ]
    target_projects = (
        set() if same else {n.lower() for n in db.scalars(select(Project.name).where(Project.owner_id == target.id))}
    )
    created = [Item(id=i, name=n, new_name=new) for i, n, new in _renamed(created_rows, target_projects, suffix)]

    memberships = db.execute(
        select(Project.id, Project.name, ProjectMember.role)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == origin.id)
        .order_by(func.lower(Project.name), Project.id)
    ).all()
    owned = [Item(id=i, name=n, role=r) for i, n, r in memberships if r == "owner"]
    others = [Item(id=i, name=n, role=r) for i, n, r in memberships if r != "owner"]

    linked = select(ProjectConnection.id).where(ProjectConnection.connection_id == Connection.id).exists()
    connection_rows = db.execute(
        select(Connection.id, Connection.name, Connection.visibility)
        .where(Connection.owner_id == origin.id, (Connection.visibility == "shared") | linked)
        .order_by(func.lower(Connection.name), Connection.id)
    ).all()
    target_connections = (
        set()
        if same
        else {n.lower() for n in db.scalars(select(Connection.name).where(Connection.owner_id == target.id))}
    )
    visibility = {cid: vis for cid, _, vis in connection_rows}
    connections = [
        Item(id=i, name=n, new_name=new, visibility=visibility[i])
        for i, n, new in _renamed([(c, n) for c, n, _ in connection_rows], target_connections, suffix)
    ]
    if not target.can("connections.share") and any(c.visibility == "shared" for c in connections):
        reasons.append("target_cannot_share")

    busy_ids = set(
        db.scalars(
            select(Run.project_id).where(
                Run.project_id.in_([p.id for p in created]), Run.status.in_(("queued", "running"))
            )
        )
    )
    busy = [p for p in created if p.id in busy_ids]
    if busy:
        reasons.append("busy")
    return TransferPlan(
        reasons=reasons,
        created_projects=created,
        owned_projects=owned,
        other_memberships=others,
        connections=connections,
        busy_projects=busy,
    )


def _repoint(db: Session, project_id: int, old: str, new: str) -> None:
    """Reescribe el prefijo de las rutas guardadas de un proyecto (ejecuciones, ficheros y plantillas)."""
    start = len(old) + 1
    for model, column in ((Run, Run.workspace_path), (Upload, Upload.path), (DocumentTemplate, DocumentTemplate.path)):
        db.execute(
            update(model)
            .where(model.project_id == project_id, column.startswith(f"{old}/", autoescape=True))
            .values({column.key: literal(new) + func.substr(column, start)})
            .execution_options(synchronize_session=False)
        )


def _journal_path(settings: Settings, journal_id: str) -> Path:
    return settings.workspace_dir / JOURNAL_DIR / f"{journal_id}.json"


def _move(settings: Settings, source: str, destination: str) -> bool:
    """Mueve la carpeta ``source`` a ``destination`` (relativas al workspace); ``False`` si no había nada que mover.

    Raises:
        FileExistsError: Ya existe ``destination`` (no se sobrescribe nunca).
    """
    src = safe_path(settings.workspace_dir, source)
    dst = safe_path(settings.workspace_dir, destination)
    if not src.exists():
        return False
    if dst.exists():
        raise FileExistsError(destination)
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    return True


def transfer_user(
    db: Session,
    origin: User,
    target: User,
    *,
    actor: User,
    remove_memberships: bool,
    settings: Settings,
    ctx: RequestContext,
) -> TransferPlan:
    """Transfiere a ``target`` lo que impide borrar ``origin`` (ver el módulo) y devuelve lo hecho.

    Raises:
        TransferBlockedError: Mismo usuario, destino inactivo, conexiones compartidas a quien no tiene ``connections.share`` o ejecuciones en
            cola o en curso en un proyecto que creó.
    """
    # Escribir primero toma el bloqueo de escritura de SQLite: nadie encola ejecuciones ni cambia miembros o
    # conexiones entre la comprobación y la transferencia.
    origin.updated_at = utcnow()
    db.flush()
    db.refresh(target)  # su estado (activo, rol) leído ya con el bloqueo tomado
    plan = transfer_preview(db, origin, target)
    if not plan.can_transfer:
        db.rollback()
        raise TransferBlockedError("Revisa los motivos antes de transferir.", **plan.as_extra())

    moves: list[dict[str, object]] = []
    for item in plan.created_projects:
        project = db.get(Project, item.id)
        if project is None:  # no puede pasar con el bloqueo tomado
            continue
        old, new = project_prefix(origin.id, project.id), project_prefix(target.id, project.id)
        project.owner_id = target.id
        if item.new_name:
            project.name = item.new_name
        _repoint(db, project.id, old, new)
        moves.append({"project_id": project.id, "from": old, "to": new})
    for item in plan.owned_projects:
        member = db.get(ProjectMember, (item.id, target.id))
        if member is None:
            db.add(ProjectMember(project_id=item.id, user_id=target.id, role="owner"))
        else:
            member.role = "owner"
    for item in plan.connections:
        connection = db.get(Connection, item.id)
        if connection is not None:
            connection.owner_id = target.id
            if item.new_name:
                connection.name = item.new_name
    removed: list[int] = []
    if remove_memberships:
        db.flush()  # el destino ya es owner donde el origen lo era: ningún proyecto se queda sin owner
        removed = list(db.scalars(select(ProjectMember.project_id).where(ProjectMember.user_id == origin.id)))
        db.execute(delete(ProjectMember).where(ProjectMember.user_id == origin.id))
    audit.record(
        db,
        action=AuditAction.USER_TRANSFER,
        ctx=ctx,
        actor_id=actor.id,
        target_type="user",
        target_id=origin.id,
        details={
            "to_user_id": target.id,
            "to_username": target.username,
            "created_projects": [p.id for p in plan.created_projects],
            "owned_projects": [p.id for p in plan.owned_projects],
            "connections": [c.id for c in plan.connections],
            "renamed": {
                **{f"project:{p.id}": p.new_name for p in plan.created_projects if p.new_name},
                **{f"connection:{c.id}": c.new_name for c in plan.connections if c.new_name},
            },
            "removed_memberships": removed,
        },
    )
    db.flush()
    _apply_moves(db, settings, moves, origin_id=origin.id, target_id=target.id)
    return plan


def _apply_moves(
    db: Session, settings: Settings, moves: list[dict[str, object]], *, origin_id: int, target_id: int
) -> None:
    """Diario → mover carpetas → confirmar → borrar el diario; si algo falla antes de confirmar, se deshace todo."""
    if not moves:
        db.commit()
        return
    journal = _journal_path(settings, new_ulid())
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(json.dumps({"origin": origin_id, "target": target_id, "moves": moves}), encoding="utf-8")
    done: list[dict[str, object]] = []
    try:
        for move in moves:
            if _move(settings, str(move["from"]), str(move["to"])):
                done.append(move)
        db.commit()
    except BaseException:
        db.rollback()
        for move in reversed(done):
            try:
                _move(settings, str(move["to"]), str(move["from"]))
            except OSError:
                logger.exception("No se pudo devolver una carpeta tras fallar la transferencia", extra={"move": move})
                raise  # se conserva el diario: el worker lo resolverá al arrancar
        journal.unlink(missing_ok=True)
        raise
    journal.unlink(missing_ok=True)


def recover_transfers(db: Session, settings: Settings) -> int:
    """Resuelve los diarios que quedaron a medias (proceso muerto entre mover y confirmar).

    Si la BD ya tiene al destino como creador, termina los movimientos; si no, devuelve las carpetas. Devuelve
    cuántos diarios ha resuelto.
    """
    folder = settings.workspace_dir / JOURNAL_DIR
    if not folder.is_dir():
        return 0
    resolved = 0
    for journal in sorted(folder.glob("*.json")):
        try:
            data = json.loads(journal.read_text(encoding="utf-8"))
            target = int(data["target"])
            for move in data["moves"]:
                project = db.get(Project, int(move["project_id"]))
                committed = project is not None and project.owner_id == target
                source, destination = (move["from"], move["to"]) if committed else (move["to"], move["from"])
                if _move(settings, str(source), str(destination)):
                    logger.warning(
                        "Transferencia interrumpida: carpeta recolocada",
                        extra={"project_id": move["project_id"], "committed": committed},
                    )
        except (OSError, ValueError, KeyError, TypeError):
            logger.exception("Diario de transferencia sin resolver", extra={"journal": journal.name})
            continue
        journal.unlink(missing_ok=True)
        resolved += 1
    return resolved


def relocate_if_transferred(db: Session, settings: Settings, project: Project, file: Path) -> Path:
    """Para quien escribe un fichero en la carpeta del proyecto y luego guarda su fila: si el proyecto se transfirió
    mientras tanto, mueve el fichero a la carpeta nueva. Llamar con el bloqueo de escritura ya tomado (tras ``flush``).
    """
    owner = db.scalar(select(Project.owner_id).where(Project.id == project.id))
    if owner is None or owner == project.owner_id:
        return file
    relative = file.relative_to(settings.workspace_dir.resolve()).as_posix()
    old, new = project_prefix(project.owner_id, project.id), project_prefix(owner, project.id)
    if not relative.startswith(f"{old}/"):
        return file
    destination = safe_path(settings.workspace_dir, new + relative[len(old) :])
    destination.parent.mkdir(parents=True, exist_ok=True)
    file.rename(destination)
    set_committed_value(project, "owner_id", owner)  # sin marcarlo como cambiado
    logger.info("Fichero recolocado tras una transferencia", extra={"project_id": project.id})
    return destination
