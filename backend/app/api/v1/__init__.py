"""API v1: auth, users, sessions y audit (Fase 1); engines, connections y admin/allowlist (Fase 2); projects,
operations y runs (Fase 3); explorer y admin/queries (Fase 4); uploads (Fase 9); document-templates (ADR-011); admin/storage (ADR-012)…

Todo método no seguro bajo ``/api/v1`` exige token CSRF (``csrf_protect``).
"""

from fastapi import APIRouter, Depends

from app.api.deps import csrf_protect
from app.api.v1 import (
    admin_allowlist,
    admin_queries,
    admin_storage,
    audit,
    auth,
    connections,
    engines,
    explorer,
    operations,
    projects,
    runs,
    sessions,
    templates,
    uploads,
    users,
)

router = APIRouter(prefix="/v1", dependencies=[Depends(csrf_protect)])
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(sessions.router)
router.include_router(audit.router)
router.include_router(engines.router)
router.include_router(connections.router)
router.include_router(admin_allowlist.router)
router.include_router(projects.router)
router.include_router(runs.project_router)
router.include_router(runs.router)
router.include_router(operations.router)
router.include_router(explorer.router)
router.include_router(explorer.project_router)
router.include_router(admin_queries.router)
router.include_router(uploads.router)
router.include_router(templates.router)
router.include_router(templates.admin_router)
router.include_router(templates.project_router)
router.include_router(admin_storage.router)
