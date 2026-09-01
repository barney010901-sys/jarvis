"""Loads prompt templates from `/prompts` at the repo root (see
prompts/README.md) — Phase 1 wrote those files but nothing loaded them
yet; ClaudeOrchestrator is the first real caller.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.config import get_settings

# backend/app/prompts_loader.py -> parents[2] is the repo root.
_DEFAULT_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def _prompts_dir() -> Path:
    configured = get_settings().prompts_dir
    return Path(configured) if configured else _DEFAULT_PROMPTS_DIR


@lru_cache
def load_prompt(name: str) -> str:
    return (_prompts_dir() / name).read_text(encoding="utf-8")
