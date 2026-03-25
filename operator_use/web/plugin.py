"""BrowserPlugin: browser automation tools + state hook."""

import logging
from typing import TYPE_CHECKING

from operator_use.plugins.base import Plugin

if TYPE_CHECKING:
    from operator_use.agent.hooks import Hooks
    from operator_use.agent.hooks.events import BeforeLLMCallContext
    from operator_use.agent.tools import ToolRegistry

logger = logging.getLogger(__name__)


class BrowserPlugin(Plugin):
    """Contributes browser automation tools and injects browser state before each LLM call."""

    name = "browser_use"

    def __init__(self, enabled: bool = False):
        self._registry: "ToolRegistry | None" = None
        self._hooks: "Hooks | None" = None
        self.browser = None
        self._enabled = enabled
        if enabled:
            self._init_sync()

    # ------------------------------------------------------------------
    # Plugin interface
    # ------------------------------------------------------------------

    def get_tools(self) -> list:
        from operator_use.web.subagent import browser_task
        return [browser_task]

    def register_tools(self, registry: "ToolRegistry") -> None:
        self._registry = registry
        if self._enabled:
            if self.browser is not None:
                registry.set_extension("browser", self.browser)
                registry.set_extension("_browser", self.browser)
            for tool in self.get_tools():
                registry.register(tool)

    def unregister_tools(self, registry: "ToolRegistry") -> None:
        for tool in self.get_tools():
            if registry.get(tool.name) is not None:
                registry.unregister(tool.name)

    def register_hooks(self, hooks: "Hooks") -> None:
        self._hooks = hooks

    def unregister_hooks(self, hooks: "Hooks") -> None:
        pass

    # ------------------------------------------------------------------
    # Enable / disable
    # ------------------------------------------------------------------

    def _init_sync(self) -> None:
        """Synchronously initialise Browser (safe to call at startup)."""
        from operator_use.web.browser.service import Browser
        from operator_use.web.browser.config import BrowserConfig
        if self.browser is None:
            self.browser = Browser(config=BrowserConfig())

    async def enable(self) -> None:
        """Dynamically enable browser_use at runtime."""
        self._enabled = True
        if self._registry is not None:
            for tool in self.get_tools():
                if self._registry.get(tool.name) is None:
                    self._registry.register(tool)
        logger.info("browser_use enabled")

    async def disable(self) -> None:
        """Dynamically disable browser_use at runtime."""
        self._enabled = False
        if self._registry is not None:
            self.unregister_tools(self._registry)
        logger.info("browser_use disabled")

    # ------------------------------------------------------------------
    # Hook handlers
    # ------------------------------------------------------------------

    async def _state_hook(self, ctx: "BeforeLLMCallContext") -> "BeforeLLMCallContext":
        from operator_use.messages import HumanMessage
        try:
            if self.browser._client is None:
                return ctx
            if self.browser._get_current_session_id() is None:
                return ctx
            state = await self.browser.get_state()
            if state:
                state_str = state.to_string()
                ctx.messages.append(HumanMessage(content=state_str))
        except Exception as e:
            logger.debug("Browser state capture failed: %s", e)
        return ctx
