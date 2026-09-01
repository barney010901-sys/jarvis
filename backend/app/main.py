"""FastAPI application entry point.

Run with: `uvicorn app.main:app --reload` (from `backend/`).
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.config import get_settings
from app.logging_config import configure_logging
from app.ws.routes import router as ws_router

configure_logging()

app = FastAPI(title="Jarvis Backend", version="0.1.0")

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(ws_router)
