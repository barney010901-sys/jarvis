import pytest

from app.permissions.models import PermissionLevel
from app.tools.filesystem import FilesystemReadTool
from app.tools.placeholders import GitHubTool
from app.tools.project_inspection import ProjectInspectionTool
from app.tools.registry import ToolRegistry, default_registry


@pytest.mark.asyncio
async def test_filesystem_read_tool_reads_existing_file(tmp_path):
    (tmp_path / "hello.txt").write_text("hello world")
    tool = FilesystemReadTool(project_root=tmp_path)

    result = await tool.run(path="hello.txt")

    assert result.success
    assert result.data["content"] == "hello world"


@pytest.mark.asyncio
async def test_filesystem_read_tool_rejects_path_traversal(tmp_path):
    tool = FilesystemReadTool(project_root=tmp_path)
    result = await tool.run(path="../outside.txt")
    assert not result.success
    assert "escapes" in result.error


@pytest.mark.asyncio
async def test_filesystem_read_tool_missing_file(tmp_path):
    tool = FilesystemReadTool(project_root=tmp_path)
    result = await tool.run(path="nope.txt")
    assert not result.success


@pytest.mark.asyncio
async def test_project_inspection_lists_files(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("b")

    tool = ProjectInspectionTool(project_root=tmp_path)
    result = await tool.run()

    assert result.success
    assert "a.txt" in result.data["files"]
    assert "sub/b.txt" in result.data["files"]


@pytest.mark.asyncio
async def test_placeholder_tool_raises_not_implemented_but_run_catches_it():
    tool = GitHubTool()
    assert tool.permission_level == PermissionLevel.SENSITIVE

    result = await tool.run(repo="x/y", title="test")

    assert not result.success
    assert "not wired" in result.error


def test_registry_register_and_get():
    registry = ToolRegistry()
    tool = GitHubTool()
    registry.register(tool)

    assert registry.get("github.create_issue") is tool
    assert registry.get("does.not.exist") is None
    assert registry.list() == [tool]


def test_registry_rejects_duplicate_names():
    registry = ToolRegistry()
    registry.register(GitHubTool())
    with pytest.raises(ValueError):
        registry.register(GitHubTool())


def test_default_registry_has_all_phase1_tools():
    registry = default_registry(".")
    names = {t.name for t in registry.list()}
    assert names == {
        "filesystem.read",
        "project.inspect",
        "github.create_issue",
        "browser.navigate",
        "web.search",
    }
