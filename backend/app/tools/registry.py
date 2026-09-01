from __future__ import annotations

from app.tools.base import Tool
from app.tools.filesystem import FilesystemReadTool
from app.tools.placeholders import BrowserTool, GitHubTool, WebSearchTool
from app.tools.project_inspection import ProjectInspectionTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list(self) -> list[Tool]:
        return list(self._tools.values())


def default_registry(project_root: str = ".") -> ToolRegistry:
    """Registry pre-populated with every Phase-1 tool."""
    registry = ToolRegistry()
    registry.register(FilesystemReadTool(project_root))
    registry.register(ProjectInspectionTool(project_root))
    registry.register(GitHubTool())
    registry.register(BrowserTool())
    registry.register(WebSearchTool())
    return registry
