"""Validación de los parámetros de conexión contra el catálogo de util_bbdd y confinamiento de rutas.

Los parámetros de tipo ruta (fichero SQLite, JAR, certificados…) solo pueden apuntar dentro de ``UBW_FILES_DIR``:
sin esto, una conexión SQLite a ``/data/config.db`` leería los hashes de contraseñas de la aplicación.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from app.core.config import Settings
from app.domain.connections.errors import ConnectionParamsError
from app.integrations.util_bbdd.catalog import EngineDetail, ParamSpec

_SQLITE_MEMORY = ":memory:"
_JDBC_HSQLDB = re.compile(r"^jdbc:hsqldb:(hsqls?|https?|file|mem):(.*)$", re.IGNORECASE)


def _check_type(spec: ParamSpec, value: Any) -> Any:
    ok = {
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "float": isinstance(value, int | float) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "object": isinstance(value, dict),
    }[spec.type]
    if not ok:
        raise ConnectionParamsError(f"«{spec.name}» debe ser de tipo {spec.type}.", field=spec.name)
    if spec.options is not None and spec.type == "string" and value not in spec.options:
        raise ConnectionParamsError(
            f"«{spec.name}» debe ser uno de: {', '.join(o or '(vacío)' for o in spec.options)}.", field=spec.name
        )
    if spec.type == "string" and len(value) > 1024:
        raise ConnectionParamsError(f"«{spec.name}» es demasiado largo.", field=spec.name)
    return value


def _relative_inside(value: str, files_dir: Path, name: str) -> str:
    """Ruta relativa a ``files_dir`` en formato POSIX, o error si sale de ella."""
    if not value.strip() or "\x00" in value:
        raise ConnectionParamsError(f"«{name}» no puede estar vacío.", field=name)
    root = files_dir.resolve()
    raw = Path(value)
    if raw.is_absolute() or PureWindowsPath(value).is_absolute() or PurePosixPath(value).is_absolute():
        candidate = raw.resolve()
    else:
        candidate = (root / value).resolve()
    if not candidate.is_relative_to(root):
        raise ConnectionParamsError(
            f"«{name}» debe ser una ruta dentro de la carpeta de ficheros del servidor (UBW_FILES_DIR).", field=name
        )
    return candidate.relative_to(root).as_posix()


def _check_jdbc_url(value: str, files_dir: Path) -> str:
    match = _JDBC_HSQLDB.match(value)
    if not match:
        raise ConnectionParamsError(
            "«jdbc_url» debe ser jdbc:hsqldb:hsql://, hsqls://, http(s)://, file: o mem:.", field="jdbc_url"
        )
    scheme, rest = match.group(1).lower(), match.group(2)
    if scheme == "file":
        path, _, options = rest.partition(";")
        relative = _relative_inside(path, files_dir, "jdbc_url")
        return f"jdbc:hsqldb:file:{relative}" + (f";{options}" if options else "")
    return value


def validate_params(engine: EngineDetail, params: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Valida y normaliza ``params`` (sin secretos) frente a la ficha del motor.

    - Solo parámetros declarados por util_bbdd; los ``secret`` (contraseña) van aparte y los ``blocked`` no se
      admiten.
    - Tipos y ``options`` del catálogo; los valores vacíos se descartan.
    - Rutas relativas a ``UBW_FILES_DIR`` (se guardan relativas).

    Raises:
        ConnectionParamsError: Con el campo afectado.
    """
    specs = {spec.name: spec for spec in engine.params}
    files_dir = settings.files_dir
    clean: dict[str, Any] = {}
    for name, value in params.items():
        spec = specs.get(name)
        if spec is None:
            raise ConnectionParamsError(f"«{name}» no es un parámetro de {engine.name}.", field=name)
        if spec.kind == "secret":
            raise ConnectionParamsError("La contraseña se envía en el campo «password», no en «params».", field=name)
        if spec.kind == "blocked":
            raise ConnectionParamsError(f"«{name}» no se admite por seguridad.", field=name)
        if value is None or value == "":
            continue
        value = _check_type(spec, value)
        if engine.db_type == "sqlite" and name == "database" and value == _SQLITE_MEMORY:
            if settings.environment == "production":
                raise ConnectionParamsError("Las BD en memoria no tienen sentido en el servidor.", field=name)
        elif spec.kind == "path":
            value = _relative_inside(value, files_dir, name)
        elif engine.db_type == "hsqldb" and name == "jdbc_url":
            value = _check_jdbc_url(value, files_dir)
        clean[name] = value
    return clean


def resolve_paths(engine: EngineDetail, params: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Convierte las rutas guardadas (relativas a ``UBW_FILES_DIR``) en absolutas para el driver."""
    root = settings.files_dir.resolve()
    kinds = {spec.name: spec.kind for spec in engine.params}
    resolved = dict(params)
    for name, value in params.items():
        if kinds.get(name) == "path" and isinstance(value, str) and value != _SQLITE_MEMORY:
            resolved[name] = str(root / value)
    jdbc = resolved.get("jdbc_url")
    if engine.db_type == "hsqldb" and isinstance(jdbc, str) and jdbc.lower().startswith("jdbc:hsqldb:file:"):
        path, _, options = jdbc[len("jdbc:hsqldb:file:") :].partition(";")
        resolved["jdbc_url"] = f"jdbc:hsqldb:file:{(root / path).as_posix()}" + (f";{options}" if options else "")
    return resolved


#: Timeouts de conexión que se fijan si el usuario no los indica (el subproceso tiene además su propio límite).
_CONNECT_TIMEOUTS: dict[str, tuple[str, int]] = {
    "postgresql": ("connect_timeout", 10),
    "mariadb": ("connect_timeout", 10),
    "mysql": ("connect_timeout", 10),
    "sqlserver": ("login_timeout", 10),
}


def with_timeouts(db_type: str, conn_params: dict[str, Any]) -> dict[str, Any]:
    name_default = _CONNECT_TIMEOUTS.get(db_type)
    if name_default is None or name_default[0] in conn_params:
        return conn_params
    return {**conn_params, name_default[0]: name_default[1]}
