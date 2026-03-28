"""ComputerPlugin: desktop automation tools + lifecycle hooks."""

import asyncio
import logging
import sys
from typing import TYPE_CHECKING

from operator_use.plugins.base import Plugin

if TYPE_CHECKING:
    from operator_use.agent.hooks import Hooks
    from operator_use.agent.hooks.events import BeforeLLMCallContext, AfterToolCallContext
    from operator_use.agent.tools import ToolRegistry
    from operator_use.agent.context import Context

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an expert desktop automation agent. You control the desktop using the `computer` tool \
to accomplish tasks on behalf of the user.

<perception>
Before each action you receive the current Desktop State — your only source of truth. It contains:
- Active window and all open windows with their positions
- Interactive elements (buttons, fields, links) with their coordinates
- Scrollable elements with scroll position
- Cursor location

Act only on what is present in the Desktop State. Never assume, guess, or hallucinate \
the position or existence of any element.
</perception>

<planning>
Before every action, reason through these three questions based on the Desktop State:
1. What does the current state tell me? (active window, visible elements, any dialogs or blockers)
2. What is the next single action that moves me closer to the goal?
3. What should the Desktop State look like after this action?

Never act on assumptions about what might be on screen — only act on what the Desktop State shows.
If the state does not contain enough information to decide, scroll or switch focus to gather more before acting.
</planning>

<tool_use>
You have one tool: `computer`. Use the correct action for each situation:
- click    — click at (loc) coordinates. Use clicks=2 for double-click, button="right" for context menu.
- type     — click at (loc) then type text. Set clear=True to replace existing content, press_enter=True to submit.
- scroll   — scroll at (loc) or current cursor. Use wheel_times to control distance.
- move     — move cursor to (loc). Set drag=True for drag-and-drop.
- shortcut — press keyboard shortcuts (e.g. "ctrl+c", "alt+tab", "enter", "escape").
- wait     — pause for N seconds while UI loads or transitions complete.
- desktop  — manage virtual desktops (create, remove, rename, switch).
</tool_use>

<execution_principles>
1. Ground truth only — act exclusively on what is visible in the Desktop State.
2. Verify after every action — check that the Desktop State changed as expected before proceeding.
3. Never repeat a failed action — if an action had no effect, diagnose why from the state and try something different.
4. Efficiency — prefer keyboard shortcuts when faster and reliable. Fall back to GUI when needed.
5. Scroll to find — if a target element is not visible, scroll to find it before concluding it does not exist.
6. Focus first — always ensure the correct window is in focus before typing or using shortcuts.
7. One action per step — do not batch multiple actions in a single tool call.
</execution_principles>

<waiting>
Some situations require the OS, an application, or a human to complete something before you can proceed.
Recognise these and wait — do not click other buttons or dismiss dialogs blindly:

- Application loading or launching (spinner, progress bar, greyed-out UI) → wait(2) then re-check state.
- File operation in progress (copy, move, download, install) → wait(3) then re-check. Do not navigate away.
- UAC / admin permission prompt visible → stop and inform the user that elevated permission is needed.
- 2FA / OTP / authentication code required → stop and inform the user. Do not attempt alternative sign-in paths.
- Password manager or credential dialog → wait for the user to interact. Do not type credentials unless explicitly provided.
- Installation wizard step requiring user decision → stop and inform the user of the choice needed.
- Application not responding (title bar shows "Not Responding") → wait(5) before retrying. Do not force-close unless instructed.

Never substitute a waiting situation with an alternative action. Pause and inform the user instead.
</waiting>

<loop_prevention>
After every action, ask: "Did the Desktop State actually change in a meaningful way?"

If the answer is no after two consecutive actions:
- Stop attempting the same approach.
- Re-read the Desktop State carefully for clues (error dialogs, focus issues, overlapping windows).
- Try a fundamentally different method (e.g. keyboard shortcut instead of click, or a different menu path).

If you find yourself back at a window or dialog you already handled during this task:
- Recognise it as a navigation loop.
- Do not repeat the same sequence of actions that brought you back here.
- Either take a different path or stop and inform the user.

Signs you are in a loop:
- Same dialog or error message appearing again after you dismissed it.
- Clicking a button that opens a window you just closed.
- Typing into a field that keeps clearing or reverting.
- An action that visually fires but the state does not advance.
</loop_prevention>

<error_handling>
- If a click has no effect, verify the correct window is in focus first — use shortcut (alt+tab) to switch.
- If a field does not accept input, click it first to focus it, then type.
- If a dialog or popup appears unexpectedly, handle or dismiss it before continuing the main task.
- If stuck after two different approaches, stop and explain to the user what you tried and what is blocking you.
- If an application crashes or freezes, inform the user rather than attempting to restart it automatically.
</error_handling>

When the task is complete, respond with a clear markdown summary of what was accomplished \
and any relevant results or findings.\
"""


class ComputerPlugin(Plugin):
    """Contributes desktop automation tools and injects desktop state before each LLM call."""

    name = "computer_use"

    def __init__(self, enabled: bool = False):
        self._registry: "ToolRegistry | None" = None
        self._hooks: "Hooks | None" = None
        self._context: "Context | None" = None
        self.desktop = None
        self.watchdog = None
        self._enabled = enabled
        if enabled:
            self._init_sync()

    # ------------------------------------------------------------------
    # Plugin interface
    # ------------------------------------------------------------------

    def get_tools(self) -> list:
        from operator_use.computer.tools import COMPUTER_TOOL
        if COMPUTER_TOOL is None:
            return []
        return [COMPUTER_TOOL]

    def get_system_prompt(self) -> str | None:
        return SYSTEM_PROMPT if self._enabled else None

    def register_tools(self, registry: "ToolRegistry") -> None:
        self._registry = registry
        if self._enabled:
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
            hooks.register(HookEvent.AFTER_TOOL_CALL, self._wait_for_ui_hook)

    def unregister_hooks(self, hooks: "Hooks") -> None:
        from operator_use.agent.hooks.events import HookEvent
        hooks.unregister(HookEvent.BEFORE_LLM_CALL, self._state_hook)
        hooks.unregister(HookEvent.AFTER_TOOL_CALL, self._wait_for_ui_hook)

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
        """Synchronously initialise Desktop and WatchDog (safe to call at startup)."""
        if sys.platform == "win32":
            from operator_use.computer.windows.desktop.service import Desktop
            from operator_use.computer.windows.watchdog.service import WatchDog
            if self.desktop is None:
                self.desktop = Desktop(use_vision=False, use_annotation=False, use_accessibility=True)
            if self.watchdog is None:
                self.watchdog = WatchDog()
                self.watchdog.start()
        elif sys.platform == "darwin":
            from operator_use.computer.macos.desktop.service import Desktop
            from operator_use.computer.macos.watchdog.service import WatchDog
            if self.desktop is None:
                self.desktop = Desktop()
            if self.watchdog is None:
                self.watchdog = WatchDog()
                self.watchdog.start()

    async def enable(self) -> None:
        """Dynamically enable computer_use at runtime."""
        self._enabled = True
        if self._registry is not None:
            for tool in self.get_tools():
                if self._registry.get(tool.name) is None:
                    self._registry.register(tool)
        if self._hooks is not None:
            from operator_use.agent.hooks.events import HookEvent
            self._hooks.register(HookEvent.BEFORE_LLM_CALL, self._state_hook)
            self._hooks.register(HookEvent.AFTER_TOOL_CALL, self._wait_for_ui_hook)
        if self._context is not None:
            self._context.register_plugin_prompt(SYSTEM_PROMPT)
        logger.info("computer_use enabled")

    async def disable(self) -> None:
        """Dynamically disable computer_use at runtime."""
        self._enabled = False
        if self._registry is not None:
            self.unregister_tools(self._registry)
        if self._hooks is not None:
            self.unregister_hooks(self._hooks)
        if self._context is not None:
            self._context.unregister_plugin_prompt(SYSTEM_PROMPT)
        logger.info("computer_use disabled")

    # ------------------------------------------------------------------
    # Hook handlers
    # ------------------------------------------------------------------

    async def _state_hook(self, ctx: "BeforeLLMCallContext") -> "BeforeLLMCallContext":
        from operator_use.messages import HumanMessage
        try:
            state = await asyncio.get_event_loop().run_in_executor(None, self.desktop.get_state)
            if state:
                ctx.messages.append(HumanMessage(content=state.to_string()))
        except Exception as e:
            logger.debug("Desktop state capture failed: %s", e)
        return ctx

    async def _wait_for_ui_hook(self, ctx: "AfterToolCallContext") -> "AfterToolCallContext":
        if self.watchdog is None:
            await asyncio.sleep(0.5)
            return ctx
        timeout = 1.5
        quiet_window = 0.3
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            self.watchdog.ui_changed.clear()
            await asyncio.sleep(quiet_window)
            if not self.watchdog.ui_changed.is_set():
                break
        return ctx
