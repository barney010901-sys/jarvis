"""SENSITIVE / not-yet-implemented tool interfaces.

These are registered with real, correct metadata (name, description, input
schema, permission level) so the orchestrator, permission gate, and tool
registry can be exercised end-to-end. `execute` raises `NotImplementedError`
on purpose — see docs/DECISIONS.md ("Do not fake this integration").
"""
from __future__ import annotations

from typing import Any

from app.permissions.models import PermissionLevel
from app.tools.base import Tool, ToolResult


class GitHubTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="github.create_issue",
            description="Create a GitHub issue or PR comment on behalf of the user.",
            input_schema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["repo", "title"],
            },
            permission_level=PermissionLevel.SENSITIVE,
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        raise NotImplementedError(
            "github.create_issue is not wired to a real GitHub integration yet. "
            "Connect it to the GitHub MCP server (or the GitHub REST API with a "
            "scoped token) in a later phase."
        )


class BrowserTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="browser.navigate",
            description="Drive a headless browser to a URL and extract content or perform an action.",
            input_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "action": {"type": "string", "description": "e.g. 'read', 'click', 'fill'"},
                },
                "required": ["url"],
            },
            permission_level=PermissionLevel.SENSITIVE,
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        raise NotImplementedError(
            "browser.navigate is not wired to a real browser-automation backend "
            "(e.g. Playwright) yet."
        )


class WebSearchTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="web.search",
            description="Search the web for up-to-date information.",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            # Reading search results is a SAFE, read-only operation.
            permission_level=PermissionLevel.SAFE,
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        raise NotImplementedError(
            "web.search is not wired to a real search provider yet."
        )
