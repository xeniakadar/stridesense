from fastapi import APIRouter

from app.api.analytics import router as analytics_router
from app.api.ask import router as ask_router
from app.api.integrations import router as integrations_router
from app.api.runs import router as runs_router

api_router = APIRouter()
api_router.include_router(runs_router)
api_router.include_router(analytics_router)
api_router.include_router(integrations_router)
api_router.include_router(ask_router)
