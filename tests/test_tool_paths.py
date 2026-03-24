import pytest

from operator_use.agent.tools.builtin.filesystem import edit_file, list_dir, read_file, write_file
from operator_use.agent.tools.builtin.patch import patch_file
from operator_use.agent.tools.builtin.terminal import terminal
from operator_use.paths import get_userdata_dir


@pytest.mark.asyncio
async def test_read_file_denies_runtime_config(tmp_path):
    config_path = get_userdata_dir() / "config.json"

    result = await read_file.ainvoke(path=str(config_path), _workspace=tmp_path)

    assert result.success is False
    assert "outside workspace" in result.error or "protected path" in result.error


@pytest.mark.asyncio
async def test_write_file_denies_outside_workspace(tmp_path):
    result = await write_file.ainvoke(
        path=str(get_userdata_dir() / "config.json"),
        content="x",
        _workspace=tmp_path,
    )

    assert result.success is False
    assert "outside workspace" in result.error or "protected path" in result.error


@pytest.mark.asyncio
async def test_edit_file_denies_outside_workspace(tmp_path):
    result = await edit_file.ainvoke(
        path=str(get_userdata_dir() / "config.json"),
        edits=[{"old_content": "a", "new_content": "b"}],
        _workspace=tmp_path,
    )

    assert result.success is False
    assert "outside workspace" in result.error or "protected path" in result.error


@pytest.mark.asyncio
async def test_patch_file_denies_outside_workspace(tmp_path):
    result = await patch_file.ainvoke(
        path=str(get_userdata_dir() / "config.json"),
        patch="@@ -1 +1 @@\n-a\n+b",
        _workspace=tmp_path,
    )

    assert result.success is False
    assert "outside workspace" in result.error or "protected path" in result.error


@pytest.mark.asyncio
async def test_list_dir_denies_parent_escape(tmp_path):
    result = await list_dir.ainvoke(path="..", _workspace=tmp_path)

    assert result.success is False
    assert "outside workspace" in result.error


@pytest.mark.asyncio
async def test_terminal_runs_from_workspace(tmp_path):
    result = await terminal.ainvoke(cmd="echo %CD%", timeout=5, _workspace=tmp_path)

    assert result.success is True
    assert str(tmp_path) in result.output


@pytest.mark.asyncio
async def test_terminal_denies_path_escape(tmp_path):
    result = await terminal.ainvoke(cmd="type ..\\secret.txt", timeout=5, _workspace=tmp_path)

    assert result.success is False
    assert "path traversal" in result.error or "outside workspace" in result.error


@pytest.mark.asyncio
async def test_terminal_denies_python_executor(tmp_path):
    result = await terminal.ainvoke(
        cmd='python -c "print(123)"',
        timeout=5,
        _workspace=tmp_path,
    )

    assert result.success is False
    assert "disallowed executor" in result.error


@pytest.mark.asyncio
async def test_read_file_denies_configured_protected_path_inside_workspace(tmp_path):
    protected_dir = tmp_path / "protected"
    protected_dir.mkdir()
    secret_file = protected_dir / "secret.txt"
    secret_file.write_text("nope", encoding="utf-8")

    result = await read_file.ainvoke(
        path="protected/secret.txt",
        _workspace=tmp_path,
        _protected_paths=[protected_dir],
    )

    assert result.success is False
    assert "protected path" in result.error
