"""Assembles a prompt-ready context string from the three memory tiers.

Phase 1: plain concatenation with section headers. Once `ClaudeProvider` is
wired into the orchestrator (Phase 2), this is what feeds its system/context
input, so the *shape* is worth getting right now even though the content
source is still an in-memory store.
"""
from __future__ import annotations

from app.memory.store import LongTermMemory, ShortTermMemory, WorkingMemory


class ContextEngine:
    def __init__(
        self,
        working_memory: WorkingMemory,
        short_term_memory: ShortTermMemory,
        long_term_memory: LongTermMemory,
    ) -> None:
        self._working = working_memory
        self._short_term = short_term_memory
        self._long_term = long_term_memory

    async def build(
        self,
        *,
        task_id: str,
        session_id: str,
        project: str,
        query: str = "",
    ) -> str:
        sections: list[str] = []

        recent = await self._short_term.recent(session_id)
        if recent:
            lines = [f"{t.role}: {t.content}" for t in recent]
            sections.append("## Recent conversation\n" + "\n".join(lines))

        if query:
            facts = await self._long_term.search(project, query)
            if facts:
                lines = [f"- {f.content}" for f in facts]
                sections.append("## Relevant long-term memory\n" + "\n".join(lines))

        plan = await self._working.get(task_id, "plan")
        if plan:
            sections.append(f"## Current plan\n{plan}")

        return "\n\n".join(sections)
