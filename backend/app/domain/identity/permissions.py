"""Catálogo fijo de permisos de los roles (ADR-014).

Un rol es un nombre y una lista de estos permisos; cada usuario tiene un rol. El acceso a cada proyecto sigue siendo
por miembros (``owner``/``editor``/``viewer``), y la cuota de almacenamiento es de cada usuario.
"""

from __future__ import annotations

from typing import Final, Literal

Permission = Literal[
    "users.manage",
    "roles.manage",
    "sessions.manage",
    "audit.read",
    "templates.manage",
    "queries.manage",
    "allowlist.manage",
    "storage.manage",
    "runs.admin",
    "connections.share",
    "sql.run",
    "ddl.apply",
    "data.write",
]

#: Orden en que se muestran (administración y, después, capacidades sobre bases de datos).
PERMISSIONS: Final[tuple[Permission, ...]] = (
    "users.manage",
    "roles.manage",
    "sessions.manage",
    "audit.read",
    "templates.manage",
    "queries.manage",
    "allowlist.manage",
    "storage.manage",
    "runs.admin",
    "connections.share",
    "sql.run",
    "ddl.apply",
    "data.write",
)

#: Grupo de cada permiso en la interfaz.
PERMISSION_GROUPS: Final[dict[Permission, Literal["admin", "databases"]]] = {
    p: ("databases" if p in ("connections.share", "sql.run", "ddl.apply", "data.write") else "admin")
    for p in PERMISSIONS
}

BuiltinRole = Literal["admin", "user"]

#: Roles base: no se borran ni cambian de permisos. «Administrador» tiene siempre todos (también los que se añadan
#: al catálogo en el futuro); «Usuario», ninguno.
BUILTIN_ROLES: Final[dict[BuiltinRole, str]] = {"admin": "Administrador", "user": "Usuario"}

#: Permisos que sustituyen a los antiguos ``users.can_*`` (la migración 0014 los convierte y se mantienen en sincronía
#: para poder volver a una imagen anterior).
LEGACY_FLAGS: Final[dict[str, Permission]] = {
    "can_run_sql": "sql.run",
    "can_apply_ddl": "ddl.apply",
    "can_write_data": "data.write",
}


def normalize(permissions: list[str] | tuple[str, ...] | frozenset[str] | set[str]) -> list[Permission]:
    """Permisos válidos de ``permissions`` en el orden del catálogo (los desconocidos se descartan)."""
    wanted = set(permissions)
    return [p for p in PERMISSIONS if p in wanted]


def unknown(permissions: list[str]) -> list[str]:
    """Los de ``permissions`` que no están en el catálogo."""
    return sorted(set(permissions) - set(PERMISSIONS))
