"""The orchestrator is the single entry point that turns a user message into
task events. It owns the task lifecycle (created -> planned -> started ->
... -> completed/failed) and is the only component that talks to both the
planner and the tool registry, gated by the permission system.

Everything downstream of this interface (the planner, memory, tools) can be
swapped without the API/WebSocket layer knowing.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class OrchestratorInterface(ABC):
    @abstractmethod
    async def handle_message(self, *, session_id: str, project: str, text: str) -> str:
        """Handle one user message. Publishes the full task.* / tool.* /
        confirmation.* event sequence on the event bus as it works, and
        returns the created task_id immediately (the caller does not block
        on completion — progress is observed via events).
        """
