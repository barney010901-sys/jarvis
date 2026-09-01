"""Real, working SAFE tool: read a text file from within a project root.

Sandboxed to `project_root` (defaults to the current working directory) so
this can't be used to read arbitrary paths on the host.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.permissions.models import PermissionLevel
from app.tools.base import Tool, ToolResult

MAX_BYTES = 200_000


class FilesystemReadTool(Tool):
    def __init__(self, project_root: str | Path = ".") -> None:
        super().__init__(
            name="filesystem.read",
            description="Read a UTF-8 text file within the project root.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relative to the project root.",
                    }
                },
                "required": ["path"],
            },
            permission_level=PermissionLevel.SAFE,
        )
        self._root = Path(project_root).resolve()

    async def execute(self, **kwargs: Any) -> ToolResult:
        rel_path = kwargs.get("path")
        if not rel_path or not isinstance(rel_path, str):
            return ToolResult.fail("'path' is required and must be a string")

        candidate = (self._root / rel_path).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError:
            return ToolResult.fail("path escapes the project root")

        if not candidate.exists():
            return ToolResult.fail(f"no such file: {rel_path}")
        if not candidate.is_file():
            return ToolResult.fail(f"not a file: {rel_path}")

        try:
            data = candidate.read_bytes()
        except OSError as exc:
            return ToolResult.fail(f"could not read file: {exc}")

        truncated = len(data) > MAX_BYTES
        text = data[:MAX_BYTES].decode("utf-8", errors="replace")
        return ToolResult.ok({"path": rel_path, "content": text, "truncated": truncated})
