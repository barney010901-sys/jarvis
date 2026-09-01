"""Proactive learning (2O): "what knowledge is likely to become useful,
based on active projects/goals/interests?" — purely local heuristics, NO
Claude calls (see docs/DECISIONS.md, "Proactive learning makes zero Claude
calls"). Gated by `feature_proactive_learning` (off by default); invoked
manually (`run_cycle`), not on a background scheduler — see
docs/PHASE_2.md for why a real scheduler is out of scope here.
"""
from __future__ import annotations

from app.knowledge.models import KnowledgeCategory
from app.knowledge.service import KnowledgeService
from app.profile.interest_engine import InterestEngine
from app.suggestions.models import Priority
from app.suggestions.service import SuggestionService

MIN_SCORE_TO_ACT = 2.0
HIGH_PRIORITY_SCORE = 5.0
MEDIUM_PRIORITY_SCORE = 3.0


class ProactiveLearningEngine:
    def __init__(
        self,
        *,
        interest_engine: InterestEngine,
        knowledge_service: KnowledgeService,
        suggestion_service: SuggestionService,
        enabled: bool,
    ) -> None:
        self._interests = interest_engine
        self._knowledge = knowledge_service
        self._suggestions = suggestion_service
        self._enabled = enabled

    async def run_cycle(self, *, project_slug: str | None = None, limit: int = 5) -> list[str]:
        """Returns the titles of suggestions created this cycle (empty if
        disabled or nothing crossed the action threshold — never raises for
        "nothing to do")."""
        if not self._enabled:
            return []

        titles: list[str] = []
        top = await self._interests.top_interests(project_slug=project_slug, limit=limit)

        for interest, score in top:
            if score < MIN_SCORE_TO_ACT:
                continue

            title = f"Explore recent developments in {interest.topic}"
            await self._knowledge.learn_from_result(
                project=project_slug,
                category=KnowledgeCategory.FUTURE_RELEVANT_KNOWLEDGE,
                title=title,
                content=(
                    f"Recurring interest detected in '{interest.topic}' "
                    f"({interest.signal_count} signals, current score {score:.2f}). "
                    "Consider reviewing current best practices, libraries, or updates "
                    "relevant to this topic."
                ),
                source="proactive_learning",
                source_type="heuristic",
                tags=[interest.topic],
                confidence=0.4,  # heuristic-generated, not verified — see 2Q
            )

            priority = (
                Priority.HIGH if score >= HIGH_PRIORITY_SCORE else Priority.MEDIUM if score >= MEDIUM_PRIORITY_SCORE else Priority.LOW
            )
            await self._suggestions.suggest(
                title=title,
                reason=f"Recurring interest in '{interest.topic}' across {interest.signal_count} interactions.",
                relevance=min(1.0, score / HIGH_PRIORITY_SCORE),
                source="proactive_learning",
                priority=priority,
                related_project=project_slug,
                confidence=0.4,
            )
            titles.append(title)

        return titles
