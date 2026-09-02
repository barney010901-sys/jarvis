"""The transmission boundary. `CommunicationService` decides WHETHER a
message may go out (classification + PolicyEngine); this is the ONLY
place that would actually put it on a wire — and there is no real wire.
No SMS/email/messaging-platform API credentials exist in this project, so
`NotConfiguredChannelAdapter.send()` raises `NotImplementedError`, exactly
like `agent/coding_agent/interface.py` and `backend/app/tools/
placeholders.py` in Phase 1/2. See docs/DECISIONS.md ("Communication
transmission is not faked").
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ChannelResult:
    delivered: bool
    detail: str


class CommunicationChannelAdapter(ABC):
    @abstractmethod
    async def send(self, *, channel: str, destination: str, message: str) -> ChannelResult: ...


class NotConfiguredChannelAdapter(CommunicationChannelAdapter):
    async def send(self, *, channel: str, destination: str, message: str) -> ChannelResult:
        raise NotImplementedError(
            f"No real transmission channel is configured for '{channel}'. Connect a real "
            "SMS/email/messaging-platform integration here before any message can actually "
            "be delivered — see docs/DECISIONS.md."
        )
