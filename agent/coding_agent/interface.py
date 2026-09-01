"""Interface for delegating a coding task to a real coding agent (Claude
Code). Intentionally NOT implemented — see docs/DECISIONS.md ("Do not fake
this integration").

## How the real integration should be connected

A real implementation should:

1. Accept a `working_directory` scoped to the project the task concerns
   (never the backend's own source tree), matching the sandboxing already
   used by `backend/app/tools/filesystem.py` and `project_inspection.py`.
2. Invoke the Claude Code CLI as a subprocess (e.g.
   `claude -p "<task>" --output-format stream-json`) with that directory as
   cwd, using `asyncio.create_subprocess_exec` so output can be streamed
   rather than buffered.
3. Parse each streamed JSON event from the CLI and re-publish it on the
   backend's `EventBus` as `tool.started` / `tool.completed` (or a
   dedicated `coding_agent.*` event type, added to `EventType` when this is
   built) so the Android app sees live progress the same way it sees any
   other tool execution.
4. Treat the CLI's own exit code and final result as the source of truth
   for success/failure — do not infer success from the request having been
   sent. This feeds the evaluation layer described in the top-level task
   spec ("do not trust an agent simply because it says done").
5. Register itself as a SENSITIVE tool in `backend/app/tools/registry.py`
   (it can modify a real project's files), so it goes through the same
   confirmation gate as `GitHubTool`/`BrowserTool`.

This module defines the contract that implementation must satisfy; it
carries no code that talks to a subprocess or the CLI.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CodingTaskResult:
    success: bool
    summary: str
    changed_files: list[str]
    raw_output: str


class CodingAgentInterface(ABC):
    @abstractmethod
    async def run_task(self, *, working_directory: str, instruction: str) -> CodingTaskResult:
        """Delegate `instruction` to a real coding agent scoped to
        `working_directory`. Must not return `success=True` without the
        underlying agent actually reporting success."""
