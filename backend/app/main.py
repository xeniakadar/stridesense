from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import api_router
from app.core.config import get_settings
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


settings = get_settings()
app = FastAPI(title="StrideSense API", version="0.0.1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# POST /ask only reads pre-generated answers in demo mode (app/api/ask.py)
DEMO_SAFE_PATHS = {"/ask"}


@app.middleware("http")
async def demo_read_only(request: Request, call_next):
    """Demo deployments are read-only: visitors browse seeded data but
    can't mutate it. get_settings() is called per-request (not the
    module-level snapshot) so tests can patch it."""
    if (
        get_settings().demo_mode
        and request.method in MUTATING_METHODS
        and request.url.path not in DEMO_SAFE_PATHS
    ):
        return JSONResponse(status_code=403, content={"detail": "Demo is read-only"})
    return await call_next(request)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/config")
async def config() -> dict[str, bool]:
    """Public runtime flags the frontend adapts to."""
    return {"demo_mode": get_settings().demo_mode}


@app.get("/health/db")
async def health_db() -> dict[str, str]:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok", "db": "reachable"}

app.include_router(api_router)
