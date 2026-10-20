"""API v1: auth, users, sessions y audit (Fase 1); engines, connections y admin/allowlist (Fase 2); projects…

Todo método no seguro bajo ``/api/v1`` exige token CSRF (``csrf_protect``).
"""

from fastapi import APIRouter, Depends

from app.api.deps import csrf_protect
from app.api.v1 import admin_allowlist, audit, auth, connections, engines, sessions, users

router = APIRouter(prefix="/v1", dependencies=[Depends(csrf_protect)])
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(sessions.router)
router.include_router(audit.router)
router.include_router(engines.router)
router.include_router(connections.router)
router.include_router(admin_allowlist.router)
