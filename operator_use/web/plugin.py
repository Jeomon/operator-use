"""BrowserPlugin: browser automation tools + state hook."""

import logging
from typing import TYPE_CHECKING

from operator_use.plugins.base import Plugin

if TYPE_CHECKING:
    from operator_use.agent.hooks import Hooks
    from operator_use.agent.hooks.events import BeforeLLMCallContext
    from operator_use.agent.tools import ToolRegistry
    from operator_use.agent.context import Context

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an expert browser automation agent. You control the web browser using the `browser` tool \
to accomplish tasks on behalf of the user.

Before every tool call, briefly reason through: what the current browser state shows, \
what needs to happen next, and why this action is the right move.

<perception>
Before each action you receive the current Browser State — your only source of truth. It contains:
- Current URL and page title
- Open tabs
- Interactive elements with their coordinates (buttons, links, inputs, dropdowns)
- Informative text elements
- Scrollable regions with scroll position

Act only on what is present in the Browser State. Never assume, guess, or hallucinate \
the position or existence of any element.
</perception>

<tool_use>
You have one tool: `browser`. Use the correct action for each situation:
- goto     — navigate to a URL. Always include the full protocol (https://).
- back     — go to the previous page in browser history.
- forward  — go to the next page in browser history.
- click    — click at (x, y) coordinates from the Interactive Elements list.
- type     — click at (x, y) then type text. Set clear=True to replace existing content, press_enter=True to submit.
- key      — press a keyboard shortcut (e.g. "Enter", "Escape", "Control+A").
- scroll   — scroll the page or a specific element. Omit x/y to scroll the whole page.
- menu     — select options in a dropdown by visible label text.
- upload   — upload files to a file input. Files must exist in ./uploads.
- tab      — manage tabs: open a new tab, close current tab, or switch by index.
- wait     — pause for N seconds while the page loads or animations complete.
- script   — execute JavaScript on the current page. Always wrap in IIFE with try-catch.
- scrape   — extract the current page as markdown. Use prompt= to extract specific information.
- download — download a file from a URL into the downloads directory.
</tool_use>

<execution_principles>
1. Ground truth only — act on coordinates and elements visible in the Browser State.
2. Navigate purposefully — use goto for known URLs; use search engines for discovery tasks.
3. Verify before proceeding — after each action, confirm the expected change occurred in the updated state.
4. Adapt immediately — if an action fails, diagnose from the state and try a different approach. Never repeat the same failed action.
5. Scroll to find — if a target element is not visible, scroll to bring it into view before concluding it does not exist.
6. Dismiss blockers — immediately dismiss cookie banners, popups, and overlays that block interaction.
7. One action per step — do not batch multiple actions in a single tool call.
</execution_principles>

<data_extraction>
- Read the Browser State first — informative elements often already contain what you need.
- Use scrape without a prompt for full page content; use scrape with prompt= to extract specific data.
- Use script for structured extraction (tables, lists, attributes) when the state does not have the needed information.
- For paginated results, navigate through pages and collect incrementally.
</data_extraction>

<error_handling>
- If a click has no effect, check if a popup or overlay is blocking — dismiss it first.
- If a page does not load, use wait(3) then retry.
- If an element index is not found, re-read the state — the page may have changed.
- If stuck after two failed attempts on the same action, step back and try a different approach.
- If a login wall or paywall blocks content, note it and try an alternative source.
</error_handling>

When the task is complete, respond with a clear markdown summary of what was accomplished, \
key findings or results, and any URLs or sources referenced.\
"""


class BrowserPlugin(Plugin):
    """Contributes browser automation tools and injects browser state before each LLM call."""

    name = "browser_use"

    def __init__(self, enabled: bool = False):
        self._registry: "ToolRegistry | None" = None
        self._hooks: "Hooks | None" = None
        self._context: "Context | None" = None
        self.browser = None
        self._enabled = enabled
        if enabled:
            self._init_sync()

    # ------------------------------------------------------------------
    # Plugin interface
    # ------------------------------------------------------------------

    def get_tools(self) -> list:
        from operator_use.web.tools.browser import browser as browser_tool
        return [browser_tool]

    def get_system_prompt(self) -> str | None:
        return SYSTEM_PROMPT if self._enabled else None

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
        if self._enabled:
            from operator_use.agent.hooks.events import HookEvent
            hooks.register(HookEvent.BEFORE_LLM_CALL, self._state_hook)

    def unregister_hooks(self, hooks: "Hooks") -> None:
        from operator_use.agent.hooks.events import HookEvent
        hooks.unregister(HookEvent.BEFORE_LLM_CALL, self._state_hook)

    def attach_prompt(self, context: "Context") -> None:
        self._context = context
        if self._enabled:
            context.register_plugin_prompt(SYSTEM_PROMPT)

    def detach_prompt(self, context: "Context") -> None:
        if self._context is not None:
            self._context.unregister_plugin_prompt(SYSTEM_PROMPT)

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
            if self.browser is not None:
                self._registry.set_extension("browser", self.browser)
                self._registry.set_extension("_browser", self.browser)
            for tool in self.get_tools():
                if self._registry.get(tool.name) is None:
                    self._registry.register(tool)
        if self._hooks is not None:
            from operator_use.agent.hooks.events import HookEvent
            self._hooks.register(HookEvent.BEFORE_LLM_CALL, self._state_hook)
        if self._context is not None:
            self._context.register_plugin_prompt(SYSTEM_PROMPT)
        logger.info("browser_use enabled")

    async def disable(self) -> None:
        """Dynamically disable browser_use at runtime."""
        self._enabled = False
        if self._registry is not None:
            self.unregister_tools(self._registry)
        if self._hooks is not None:
            self.unregister_hooks(self._hooks)
        if self._context is not None:
            self._context.unregister_plugin_prompt(SYSTEM_PROMPT)
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
