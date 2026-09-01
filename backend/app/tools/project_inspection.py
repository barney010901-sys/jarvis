"""Real, working SAFE tool: list files under the project root.

Used by the planner/orchestrator to build "project awareness" without
needing any external service.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.permissions.models import PermissionLevel
from app.tools.base import Tool, ToolResult

DEFAULT_IGNORE = {".git", "node_modules", "__pycache__", ".venv", "venv", ".expo"}
MAX_ENTRIES = 2_000


class ProjectInspectionTool(Tool):
    def __init__(self, project_root: str | Path = ".") -> None:
        super().__init__(
            name="project.inspect",
            description="List files under the project root, for building project awareness.",
            input_schema={
                "type": "object",
                "properties": {
                    "subpath": {
                        "type": "string",
                        "description": "Optional subdirectory, relative to the project root.",
                    }
                },
            },
            permission_level=PermissionLevel.SAFE,
        )
        self._root = Path(project_root).resolve()

    async def execute(self, **kwargs: Any) -> ToolResult:
        subpath = kwargs.get("subpath") or "."
        base = (self._root / subpath).resolve()
        try:
            base.relative_to(self._root)
        except ValueError:
            return ToolResult.fail("subpath escapes the project root")
        if not base.exists() or not base.is_dir():
            return ToolResult.fail(f"not a directory: {subpath}")

        entries: list[str] = []
        for path in sorted(base.rglob("*")):
            if any(part in DEFAULT_IGNORE for part in path.parts):
                continue
            entries.append(str(path.relative_to(self._root)))
            if len(entries) >= MAX_ENTRIES:
                break

        return ToolResult.ok({"root": str(self._root), "files": entries, "count": len(entries)})
