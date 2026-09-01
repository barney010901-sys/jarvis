"""Habit/workflow detection (2N): recognizes a repeated ordered sequence of
tool calls as a reusable workflow — deterministic, no inference about
sensitive personal attributes, no NLP.
"""
from __future__ import annotations

from app.profile.interface import ProfileStore
from app.profile.models import Workflow

CONFIRM_AFTER_EVIDENCE = 3


class WorkflowDetector:
    def __init__(self, store: ProfileStore) -> None:
        self._store = store

    async def observe(self, tool_sequence: list[str], *, project_slug: str | None = None) -> Workflow | None:
        """Call once per completed task with the ordered list of tool
        names it actually executed. Sequences shorter than 2 tools aren't
        a "workflow" — returns None without storing anything."""
        sequence = [t for t in tool_sequence if t]
        if len(sequence) < 2:
            return None

        name = " -> ".join(sequence)
        workflow, _created = await self._store.upsert_workflow(name, sequence, project_slug)

        if not workflow.confirmed and workflow.evidence_count >= CONFIRM_AFTER_EVIDENCE:
            await self._store.set_workflow_confirmed(workflow.id, True)
            workflow.confirmed = True

        return workflow
