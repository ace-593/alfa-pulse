from fastapi import APIRouter

from app.api.v1 import auth, companies, digests, ingestion, jobs, materials

router = APIRouter(prefix="/api/v1")
for module in [auth, companies, digests, materials, jobs, ingestion]:
    router.include_router(module.router)
