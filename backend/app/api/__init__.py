from fastapi import APIRouter

from app.api.analytics import router as analytics_router
from app.api.runs import router as runs_router

api_router = APIRouter()
api_router.include_router(runs_router)
api_router.include_router(analytics_router)
