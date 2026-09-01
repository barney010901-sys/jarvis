"""REST endpoints. Health check is public; everything else requires the
bearer token (see app/auth)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependency import require_bearer_token
from app.deps import get_confirmation_manager, get_orchestrator

router = APIRouter()


class MessageRequest(BaseModel):
    session_id: str
    project: str = "default"
    text: str


class MessageResponse(BaseModel):
    task_id: str


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/messages", response_model=MessageResponse)
async def send_message(body: MessageRequest, _token: str = Depends(require_bearer_token)) -> MessageResponse:
    """REST fallback for sending a message. Progress is observed via the
    `/ws` event stream, not this response — this only returns the task_id."""
    task_id = await get_orchestrator().handle_message(session_id=body.session_id, project=body.project, text=body.text)
    return MessageResponse(task_id=task_id)


@router.post("/confirmations/{confirmation_id}/approve")
async def approve_confirmation(confirmation_id: str, _token: str = Depends(require_bearer_token)) -> dict[str, str]:
    try:
        await get_confirmation_manager().approve(confirmation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "approved"}


@router.post("/confirmations/{confirmation_id}/reject")
async def reject_confirmation(confirmation_id: str, _token: str = Depends(require_bearer_token)) -> dict[str, str]:
    try:
        await get_confirmation_manager().reject(confirmation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "rejected"}
