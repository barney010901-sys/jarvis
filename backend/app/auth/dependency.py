"""Placeholder bearer-token auth. See docs/DECISIONS.md.

Swap this module out for real auth (OAuth/session) later; nothing outside
`app/auth` should need to change since routes only depend on
`require_bearer_token`.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

_bearer_scheme = HTTPBearer(auto_error=False)


async def require_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    settings = get_settings()
    if credentials is None or credentials.credentials != settings.jarvis_api_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing bearer token")
    return credentials.credentials
