"""FastAPI application entry point.

Run with: `PYTHONPATH=.. uvicorn app.main:app --reload` (from `backend/`) —
see backend/README.md for why `..` (the repo root) needs to be on
PYTHONPATH: the backend imports the `agent` package, which lives outside
`backend/`.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.phase3_routes import router as phase3_router
from app.api.routes import router as api_router
from app.config import get_settings
from app.deps import initialize as initialize_deps
from app.deps import shutdown as shutdown_deps
from app.logging_config import configure_logging
from app.ws.routes import router as ws_router

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize_deps()
    yield
    await shutdown_deps()


app = FastAPI(title="Jarvis Backend", version="0.2.0", lifespan=lifespan)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(phase3_router)
app.include_router(ws_router)
