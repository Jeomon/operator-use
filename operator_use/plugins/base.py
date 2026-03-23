"""Plugin base class."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from operator_use.tools import Tool
    from operator_use.agent.hooks import Hooks
    from operator_use.agent.tools import ToolRegistry
    from operator_use.agent.context import Context


class Plugin:
    """Base plugin. Override to contribute tools, system prompt sections, and hooks."""

    name: str = ""

    # ------------------------------------------------------------------
    # Override these in subclasses
    # ------------------------------------------------------------------

    def get_tools(self) -> "list[Tool]":
        """Return tools this plugin contributes."""
        return []

    def get_system_prompt(self) -> str | None:
        """Return a system prompt section for this plugin, or None."""
        return None

    def register_hooks(self, hooks: "Hooks") -> None:
        """Register hook handlers onto the agent's Hooks instance."""
        pass

    def unregister_hooks(self, hooks: "Hooks") -> None:
        """Unregister hook handlers from the agent's Hooks instance."""
        pass

    # ------------------------------------------------------------------
    # Default implementations — agent calls these
    # ------------------------------------------------------------------

    def register_tools(self, registry: "ToolRegistry") -> None:
        for tool in self.get_tools():
            registry.register(tool)

    def unregister_tools(self, registry: "ToolRegistry") -> None:
        for tool in self.get_tools():
            registry.unregister(tool.name)

    def attach_prompt(self, context: "Context") -> None:
        if section := self.get_system_prompt():
            context.register_plugin_prompt(section)

    def detach_prompt(self, context: "Context") -> None:
        if section := self.get_system_prompt():
            context.unregister_plugin_prompt(section)
