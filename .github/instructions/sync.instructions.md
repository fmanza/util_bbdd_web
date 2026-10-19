---
applyTo: "CHANGELOG.md,backend/pyproject.toml,backend/app/__init__.py,frontend/package.json"
---
# Sincronización de versión

La versión de util_bbdd_web vive en **cuatro** sitios y deben coincidir:

1. `CHANGELOG.md` — encabezado `## [X.Y.Z] - AAAA-MM-DD`
2. `backend/pyproject.toml` — `[project] version`
3. `backend/app/__init__.py` — `__version__`
4. `frontend/package.json` — `version` (y `package-lock.json` tras `npm install`)

Política hasta 1.0: una MINOR por fase cerrada del ROADMAP (`0.<fase+1>.0`); PATCH para hotfix.
La versión de util_bbdd consumida se cambia solo en `backend/pyproject.toml` (dependencia y `[tool.uv.sources]`)
y el wheel de `vendor/wheels/`, con nota en el CHANGELOG (ADR-006).
