"""Evaluation engine (2U): "do not assume completion." Deterministic
checks, not a second Claude call — matches 2E's cost hierarchy (see
docs/DECISIONS.md, "Evaluation stays deterministic").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.planner.interface import PlanStep
from app.tools.base import ToolResult
from app.tools.registry import ToolRegistry


class EvaluationVerdict(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


@dataclass
class EvaluationResult:
    verdict: EvaluationVerdict
    checks: list[CheckResult] = field(default_factory=list)


class EvaluationEngine:
    def __init__(self, tool_registry: ToolRegistry | None = None) -> None:
        self._tools = tool_registry

    async def evaluate(
        self,
        *,
        plan_steps: list[PlanStep],
        tool_results: list[ToolResult],
        response_text: str,
    ) -> EvaluationResult:
        checks: list[CheckResult] = []

        tools_ok = all(r.success for r in tool_results) if tool_results else True
        checks.append(
            CheckResult(
                "tools_succeeded",
                tools_ok,
                f"{sum(1 for r in tool_results if r.success)}/{len(tool_results)} tool(s) succeeded"
                if tool_results
                else "no tools executed",
            )
        )

        response_ok = bool(response_text and response_text.strip())
        checks.append(CheckResult("response_non_empty", response_ok, "response present" if response_ok else "no response text generated"))

        file_check = await self._check_expected_files(plan_steps)
        if file_check is not None:
            checks.append(file_check)

        if not tools_ok:
            verdict = EvaluationVerdict.FAILED
        elif not response_ok:
            verdict = EvaluationVerdict.NEEDS_REVIEW
        elif file_check is not None and not file_check.passed:
            verdict = EvaluationVerdict.PARTIAL
        else:
            verdict = EvaluationVerdict.SUCCESS

        return EvaluationResult(verdict=verdict, checks=checks)

    async def _check_expected_files(self, plan_steps: list[PlanStep]) -> CheckResult | None:
        """If the plan declared an `expected_file` for any step (2U: "files
        exist"), verify it via the real filesystem.read tool rather than
        trusting the plan/response. Not applicable (returns None) when no
        step declares one."""
        expected_files = [getattr(s, "expected_file", None) for s in plan_steps]
        expected_files = [f for f in expected_files if f]
        if not expected_files or self._tools is None:
            return None

        tool = self._tools.get("filesystem.read")
        if tool is None:
            return None

        details = []
        all_found = True
        for path in expected_files:
            result = await tool.run(path=path)
            found = result.success
            all_found = all_found and found
            details.append(f"{path}: {'found' if found else 'missing'}")

        return CheckResult("expected_files_exist", all_found, "; ".join(details))
