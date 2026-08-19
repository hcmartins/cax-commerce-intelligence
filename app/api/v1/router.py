from fastapi import APIRouter

from app.api.v1 import health, opportunities, runs

router = APIRouter()
router.include_router(health.router)
router.include_router(runs.router)
router.include_router(opportunities.router)
