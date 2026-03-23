from pathlib import Path

_DIR = Path.home() / ".operator-use"


def get_userdata_dir() -> Path:
    """Return the user data directory: ~/.operator-use"""
    return _DIR


def get_workspaces_dir() -> Path:
    """Return the multi-agent workspaces directory: ~/.operator-use/workspaces"""
    return _DIR / "workspaces"


def get_named_workspace_dir(name: str) -> Path:
    """Return a named agent's workspace directory: ~/.operator-use/workspaces/<name>"""
    return get_workspaces_dir() / name
