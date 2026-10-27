"""Implementaciones de las operaciones del catálogo (``app.domain.runs.operations``), ejecutadas en el subproceso."""

from __future__ import annotations

from collections.abc import Callable

from app.jobs.context import JobContext
from app.jobs.operations import bulk, compare, documentation, dump, migrate, noop

IMPLEMENTATIONS: dict[str, Callable[[JobContext], None]] = {
    "noop": noop.run,
    "documentation": documentation.run_documentation,
    "relationship_graph": documentation.run_relationship_graph,
    "compare": compare.run,
    "migrate_plan": migrate.run_plan,
    "migrate_apply": migrate.run_apply,
    "dump_preview": dump.run_preview,
    "dump_apply": dump.run_apply,
    "dump_restore": dump.run_restore,
    "bulk_preview": bulk.run_preview,
    "bulk_apply": bulk.run_apply,
}
