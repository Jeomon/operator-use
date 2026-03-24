"""Minimal governance helpers for tool execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Any


TOOL_SCOPE_ALIASES = {
    "read_file": "filesystem.read",
    "write_file": "filesystem.write",
    "edit_file": "filesystem.edit",
    "list_dir": "filesystem.list",
    "patch_file": "filesystem.patch",
    "web_search": "web.search",
    "web_fetch": "web.fetch",
    "terminal": "terminal.exec",
    "cron": "cron.manage",
    "process": "process.manage",
    "control_center": "control.manage",
    "subagents": "agents.subagents",
    "localagents": "agents.local",
    "acpagents": "agents.acp",
    "channel": "channel.send",
    "intermediate_message": "message.intermediate",
    "react_message": "message.react",
    "send_file": "message.file",
}


@dataclass(slots=True)
class GovernanceProfile:
    """Defines which tools an agent is allowed to execute."""

    allowed_tools: list[str] = field(default_factory=list)
    parent: "GovernanceProfile | None" = None

    def allows(self, tool_name: str) -> bool:
        if self.allowed_tools and not any(
            fnmatch(identifier, pattern)
            for pattern in self.allowed_tools
            for identifier in self.identifiers_for(tool_name)
        ):
            return False
        if self.parent is not None:
            return self.parent.allows(tool_name)
        return True

    def scoped(self, allowed_tools: list[str] | None = None) -> "GovernanceProfile":
        if not allowed_tools:
            return self
        return GovernanceProfile(allowed_tools=list(allowed_tools), parent=self)

    def with_parent(self, parent: "GovernanceProfile | None") -> "GovernanceProfile":
        if parent is None:
            return self
        return GovernanceProfile(allowed_tools=list(self.allowed_tools), parent=parent)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"allowed_tools": list(self.allowed_tools)}
        if self.parent is not None:
            data["parent"] = self.parent.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "GovernanceProfile | None":
        if not data:
            return None
        parent = cls.from_dict(data.get("parent"))
        return cls(
            allowed_tools=list(data.get("allowed_tools") or []),
            parent=parent,
        )

    @staticmethod
    def identifiers_for(tool_name: str) -> set[str]:
        identifiers = {tool_name}
        alias = TOOL_SCOPE_ALIASES.get(tool_name)
        if alias:
            identifiers.add(alias)
        return identifiers
