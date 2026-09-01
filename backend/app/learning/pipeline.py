"""Ties together correction detection, interest signals, workflow
detection, and knowledge extraction (2H/2I/2L/2N) — the "what do we learn
from this" logic, kept out of the orchestrator so ClaudeOrchestrator stays
focused on task flow.
"""
from __future__ import annotations

import logging

from app.evaluation.engine import EvaluationResult, EvaluationVerdict
from app.knowledge.models import KnowledgeCategory
from app.knowledge.service import KnowledgeService
from app.learning.correction_detector import CorrectionCandidate, CorrectionDetector
from app.planner.interface import PlanStep
from app.profile.interest_engine import InterestEngine
from app.profile.workflow_detector import WorkflowDetector

logger = logging.getLogger(__name__)

_TITLE_MAX_LEN = 120
_CONTENT_MAX_LEN = 800


def _truncate(text: str, max_len: int) -> str:
    text = text.strip()
    return text if len(text) <= max_len else text[: max_len - 1].rstrip() + "…"


class LearningPipeline:
    def __init__(
        self,
        *,
        knowledge_service: KnowledgeService,
        interest_engine: InterestEngine,
        workflow_detector: WorkflowDetector,
        correction_detector: CorrectionDetector | None = None,
    ) -> None:
        self._knowledge = knowledge_service
        self._interests = interest_engine
        self._workflows = workflow_detector
        self._corrections = correction_detector or CorrectionDetector()

    async def on_user_message(
        self, *, project: str, text: str, known_topics: list[str] = ()
    ) -> CorrectionCandidate | None:
        """Called once per incoming user message, before planning. Returns
        the detected correction (if any) so the caller can log/observe it."""
        candidate = self._corrections.detect(text)
        if candidate is not None:
            logger.info("Detected user correction: use %r instead of %r", candidate.new_term, candidate.old_term)
            await self._knowledge.apply_correction(
                project=project, old_term=candidate.old_term, new_term=candidate.new_term, raw_text=text
            )

        lowered = text.lower()
        for topic in known_topics:
            if topic and topic.lower() in lowered:
                await self._interests.record_signal(topic, project_slug=project)

        return candidate

    async def on_task_completed(
        self,
        *,
        project: str,
        request: str,
        plan_steps: list[PlanStep],
        evaluation: EvaluationResult,
        response_text: str,
    ) -> None:
        """Called once per completed task, after evaluation (2H): "do not
        blindly trust every Claude response" — only SUCCESS gets stored as
        reusable knowledge; workflow evidence is recorded regardless of
        verdict (a workflow is just "steps taken", not a claim of success)."""
        tool_sequence = [s.tool_name for s in plan_steps if s.tool_name]
        if tool_sequence:
            await self._workflows.observe(tool_sequence, project_slug=project)

        if evaluation.verdict != EvaluationVerdict.SUCCESS:
            return

        await self._knowledge.learn_from_result(
            project=project,
            category=KnowledgeCategory.SUCCESSFUL_TASKS,
            title=_truncate(request, _TITLE_MAX_LEN),
            content=_truncate(response_text, _CONTENT_MAX_LEN),
            source="claude_response",
            source_type="claude_response",
            confidence=0.6,
        )
