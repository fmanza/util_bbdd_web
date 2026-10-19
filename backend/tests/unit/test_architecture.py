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
