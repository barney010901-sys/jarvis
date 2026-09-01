"""Assembles a prompt-ready context bundle from memory, knowledge, and
profile (2D). Phase 1 shipped a plain-string version that concatenated the
three memory tiers and was never actually called (see docs/DECISIONS.md,
"Phase 1 ContextEngine was unused"). Phase 2 wires it into
ClaudeOrchestrator and extends it — same class, same constructor shape for
the three memory args, extended with optional knowledge/profile sources —
rather than replacing it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.knowledge.service import KnowledgeService
from app.memory.store import LongTermMemory, ShortTermMemory, WorkingMemory
from app.profile.interface import ProfileStore

DEFAULT_MAX_RECENT_TURNS = 12


@dataclass
class ContextBundle:
    """What ClaudeOrchestrator actually sends to the provider, plus enough
    metadata (2E: "context size") to log/observe without re-parsing text."""

    text: str
    included: dict[str, int] = field(default_factory=dict)
    history_truncated: bool = False

    def is_empty(self) -> bool:
        return not self.text.strip()


class ContextEngine:
    def __init__(
        self,
        working_memory: WorkingMemory,
        short_term_memory: ShortTermMemory,
        long_term_memory: LongTermMemory,
        *,
        knowledge_service: KnowledgeService | None = None,
        profile_store: ProfileStore | None = None,
    ) -> None:
        self._working = working_memory
        self._short_term = short_term_memory
        self._long_term = long_term_memory
        self._knowledge = knowledge_service
        self._profile = profile_store

    async def build(
        self,
        *,
        task_id: str,
        session_id: str,
        project: str,
        query: str = "",
        max_recent_turns: int = DEFAULT_MAX_RECENT_TURNS,
    ) -> ContextBundle:
        sections: list[str] = []
        included: dict[str, int] = {}

        # 1) Recent conversation — capped, with a local (non-Claude) note
        # when older turns are dropped rather than summarized by a model
        # call (see docs/DECISIONS.md, "History summarization stays local").
        recent = await self._short_term.recent(session_id, limit=max_recent_turns * 3)
        truncated = len(recent) > max_recent_turns
        kept = recent[-max_recent_turns:] if truncated else recent
        if kept:
            header = "## Recent conversation"
            if truncated:
                header += f"\n_(earlier {len(recent) - len(kept)} turn(s) omitted)_"
            lines = [f"{t.role}: {t.content}" for t in kept]
            sections.append(header + "\n" + "\n".join(lines))
            included["conversation_turns"] = len(kept)

        # 2) Relevant long-term memory — deduplicated by content.
        if query:
            facts = await self._long_term.search(project, query)
            seen: set[str] = set()
            unique = [f for f in facts if not (f.content in seen or seen.add(f.content))]
            if unique:
                lines = [f"- {f.content}" for f in unique]
                sections.append("## Relevant long-term memory\n" + "\n".join(lines))
                included["long_term_facts"] = len(unique)

        # 3) Relevant knowledge (2F) — only if a KnowledgeService was wired in.
        if query and self._knowledge is not None:
            records = await self._knowledge.retrieve_relevant(project=project, query=query)
            if records:
                lines = [f"- [{r.category.value}] {r.title}: {r.content} (confidence {r.confidence:.2f})" for r in records]
                sections.append("## Relevant knowledge\n" + "\n".join(lines))
                included["knowledge_records"] = len(records)

        # 4) User preferences + active project summary (2J/2K).
        if self._profile is not None:
            prefs = await self._profile.list_preferences()
            if prefs:
                lines = [f"- {p.key}: {p.value}" for p in prefs]
                sections.append("## User preferences\n" + "\n".join(lines))
                included["preferences"] = len(prefs)

            proj = await self._profile.get_project(project)
            if proj:
                lines = [f"Project: {proj.name} (status: {proj.status})"]
                if proj.goals:
                    lines.append("Goals: " + ", ".join(proj.goals))
                if proj.technologies:
                    lines.append("Technologies: " + ", ".join(proj.technologies))
                sections.append("## Project context\n" + "\n".join(lines))
                included["project_context"] = 1

        # 5) Current plan, if one exists for this task (stored as plain
        # dicts by the orchestrator — see docs/DECISIONS.md, "Working
        # memory stores plain data, not live objects").
        plan = await self._working.get(task_id, "plan")
        if plan:
            if isinstance(plan, list):
                lines = [f"{i + 1}. {step.get('description', step)}" for i, step in enumerate(plan)]
                sections.append("## Current plan\n" + "\n".join(lines))
                included["plan_steps"] = len(plan)
            else:
                sections.append(f"## Current plan\n{plan}")
                included["plan_steps"] = 1

        return ContextBundle(text="\n\n".join(sections), included=included, history_truncated=truncated)
