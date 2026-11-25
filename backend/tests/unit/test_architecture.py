"""Reglas de arquitectura comprobadas sobre el código (ADR-006)."""

from __future__ import annotations

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "app"
ANTI_CORRUPTION = APP_DIR / "integrations" / "util_bbdd"


def _imports_util_bbdd(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name.split(".")[0] == "util_bbdd" for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.level == 0 and (node.module or "").split(".")[0] == "util_bbdd":
            return True
    return False


def test_only_anti_corruption_layer_imports_util_bbdd() -> None:
    offenders = [
        str(p.relative_to(APP_DIR))
        for p in APP_DIR.rglob("*.py")
        if not p.is_relative_to(ANTI_CORRUPTION) and _imports_util_bbdd(p)
    ]

    assert offenders == [], f"Solo app/integrations/util_bbdd puede importar util_bbdd: {offenders}"


def _app_imports(path: Path) -> set[str]:
    """Paquetes ``app.<x>`` (y librerías de primer nivel) que importa un módulo."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
    return names


FORBIDDEN = {
    "workspace": ("app.db", "app.domain", "app.api", "app.jobs", "app.integrations", "fastapi", "sqlalchemy"),
    "domain": ("app.api", "app.jobs", "fastapi"),
    "api": ("app.jobs",),
    "integrations": ("app.api", "app.domain", "app.jobs"),
}


def test_layer_dependencies() -> None:
    offenders = []
    for package, forbidden in FORBIDDEN.items():
        for path in (APP_DIR / package).rglob("*.py"):
            for name in _app_imports(path):
                if any(name == f or name.startswith(f"{f}.") for f in forbidden):
                    offenders.append(f"{path.relative_to(APP_DIR)} -> {name}")

    assert offenders == [], f"Dependencias entre capas no permitidas (.ai/architecture.md): {offenders}"


#: Módulos que pueden leer las columnas antiguas ``users.role`` / ``users.can_*`` (ADR-014): el modelo, que las mantiene
#: en sincronía, y la migración que las convierte.
LEGACY_ALLOWED = {APP_DIR / "db" / "models.py"}


def test_permissions_come_from_the_role() -> None:
    """Nada vuelve a comparar con ``role == "admin"`` ni lee ``can_run_sql``/``can_apply_ddl``/``can_write_data``: los
    permisos se consultan con ``user.can(...)`` y los routers con ``require_permission`` (ADR-014)."""
    offenders = []
    for path in APP_DIR.rglob("*.py"):
        if path in LEGACY_ALLOWED:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Attribute) and node.attr in {
                "can_run_sql",
                "can_apply_ddl",
                "can_write_data",
                "legacy_role",
                "legacy_can_run_sql",
                "legacy_can_apply_ddl",
                "legacy_can_write_data",
            }:
                offenders.append(f"{path.relative_to(APP_DIR)}:{node.lineno} .{node.attr}")
            if (
                isinstance(node, ast.Compare)
                and isinstance(node.left, ast.Attribute)
                and node.left.attr == "role"
                and any(isinstance(c, ast.Constant) and c.value in {"admin", "user"} for c in node.comparators)
            ):
                offenders.append(f"{path.relative_to(APP_DIR)}:{node.lineno} role == 'admin'/'user'")
            if isinstance(node, ast.Name) and node.id in {"AdminUser", "require_admin"}:
                offenders.append(f"{path.relative_to(APP_DIR)}:{node.lineno} {node.id}")

    assert offenders == [], f"Permisos fuera del rol (ADR-014): {offenders}"
