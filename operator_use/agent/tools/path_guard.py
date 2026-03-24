"""Shared path restrictions for filesystem, patch, and terminal tools."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import operator_use

from operator_use.paths import get_named_workspace_dir, get_userdata_dir


class PathAccessError(ValueError):
    """Raised when a path or command violates path restrictions."""


_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_TRAVERSAL_RE = re.compile(r"(^|[\\/\s])\.\.([\\/]|$)")
_PATH_TOKEN_RE = re.compile(r'"[^"]+"|\'[^\']+\'|\S+')
_DISALLOWED_EXECUTORS = {
    "python",
    "python3",
    "py",
    "node",
    "perl",
    "ruby",
    "powershell",
    "pwsh",
    "bash",
    "sh",
}


def get_workspace_root(**kwargs) -> Path:
    workspace = kwargs.get("_workspace") or get_named_workspace_dir("operator")
    return Path(workspace).expanduser().resolve()


def _normalize_paths(paths: Iterable[str | Path]) -> tuple[Path, ...]:
    normalized: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        resolved = Path(path).expanduser().resolve()
        key = str(resolved).lower()
        if key in seen:
            continue
        normalized.append(resolved)
        seen.add(key)
    return tuple(normalized)


def default_protected_roots() -> tuple[Path, ...]:
    codebase = Path(operator_use.__file__).resolve().parent.parent
    userdata = get_userdata_dir().resolve()
    return _normalize_paths((
        codebase,
        userdata / "config.json",
    ))


def get_protected_roots(*, protected_paths: Iterable[str | Path] | None = None) -> tuple[Path, ...]:
    if protected_paths is None:
        return default_protected_roots()
    return _normalize_paths(protected_paths)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _candidate_real_path(candidate: Path) -> Path:
    real_parent = candidate.parent.resolve()
    return (real_parent / candidate.name).resolve(strict=False)


def ensure_allowed_path(
    path: str | Path,
    *,
    workspace: Path,
    protected_paths: Iterable[str | Path] | None = None,
) -> Path:
    workspace = workspace.expanduser().resolve()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = workspace / candidate
    candidate = candidate.resolve(strict=False)
    real_candidate = _candidate_real_path(candidate)

    if not _is_within(real_candidate, workspace):
        raise PathAccessError(f"Access denied - path outside workspace: {real_candidate}")

    for protected in get_protected_roots(protected_paths=protected_paths):
        if real_candidate == protected or _is_within(real_candidate, protected):
            raise PathAccessError(f"Access denied - protected path: {real_candidate}")

    return real_candidate


def ensure_allowed_directory(
    path: str | Path,
    *,
    workspace: Path,
    protected_paths: Iterable[str | Path] | None = None,
) -> Path:
    resolved = ensure_allowed_path(path, workspace=workspace, protected_paths=protected_paths)
    if not resolved.exists():
        raise PathAccessError(f"Directory not found: {resolved}")
    if not resolved.is_dir():
        raise PathAccessError(f"Path is not a directory: {resolved}")
    return resolved


def validate_terminal_command(
    command: str,
    *,
    workspace: Path,
    protected_paths: Iterable[str | Path] | None = None,
) -> Path:
    workspace = workspace.expanduser().resolve()
    if _TRAVERSAL_RE.search(command):
        raise PathAccessError("Command contains path traversal outside the workspace")

    tokens = [token.strip("\"'") for token in _PATH_TOKEN_RE.findall(command)]
    if tokens:
        executable = tokens[0].lower()
        if executable in _DISALLOWED_EXECUTORS:
            raise PathAccessError(f"Command uses disallowed executor '{tokens[0]}'")

    for token in tokens[1:]:
        if not token or token.startswith("-"):
            continue
        if token in {".", ".\\"}:
            continue
        if (
            token.startswith(("~", "/", "\\")) or
            _WINDOWS_DRIVE_RE.match(token) or
            "/" in token or
            "\\" in token or
            token.startswith(".")
        ):
            ensure_allowed_path(token, workspace=workspace, protected_paths=protected_paths)

    return workspace
