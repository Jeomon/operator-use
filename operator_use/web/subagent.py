"""browser_task tool — runs browser automation in an isolated context window."""

import logging

from pydantic import BaseModel, Field
from operator_use.tools import Tool, ToolResult


class BrowserTask(BaseModel):
    task: str = Field(
        ..., description="Full description of the browser automation task to perform."
    )
    keep_open: bool = Field(
        default=True, description="Keep the browser open after the task completes."
    )


from operator_use.agent.tools import ToolRegistry
from operator_use.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 30

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


@Tool(
    name="browser_task",
    description=(
        "Delegate a browser automation task to an isolated agent with its own context window. "
        "Chrome launches automatically if not already running. "
        "Describe the full task — the agent handles all browser interactions and returns a clean result. "
        "The browser stays open by default so the user can see the result."
    ),
    model=BrowserTask,
)
async def browser_task(task: str, keep_open: bool = True, **kwargs) -> ToolResult:
    llm = kwargs.get("_llm")
    if llm is None:
        return ToolResult.error_result("No LLM available.")

    from operator_use.web.browser.service import Browser
    from operator_use.web.browser.config import BrowserConfig
    from operator_use.web.plugin import BrowserPlugin
    from operator_use.web.tools.browser import browser as browser_tool
    from operator_use.agent.hooks.events import BeforeLLMCallContext
    from operator_use.agent.loop import AgentLoop
    from operator_use.web.loop import LoopGuard

    existing_browser: Browser | None = kwargs.get("_browser")
    if existing_browser is not None and existing_browser._client is not None:
        browser = existing_browser
        owns_browser = False
    else:
        import os

        profile_dir = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~/.local/share")),
            "Operator",
            "chrome-debug-profile",
        )
        config = BrowserConfig(attach_to_existing=True, cdp_port=9222, user_data_dir=profile_dir)
        browser = Browser(config=config)
        owns_browser = True

    plugin = BrowserPlugin(enabled=False)
    plugin.browser = browser

    registry = ToolRegistry()
    registry.register_tools([browser_tool])
    registry.set_extension("browser", browser)
    registry.set_extension("_llm", llm)

    await browser.ensure_open()

    loop_guard = LoopGuard()

    async def before_call(messages, iteration):
        ctx = BeforeLLMCallContext(session=None, messages=messages, iteration=iteration)
        await plugin._state_hook(ctx)
        return ctx.messages

    async def after_tool(tc, tr):
        try:
            page_state = await browser.get_state()
            if page_state and page_state.current_tab:
                loop_guard.record_page(page_state.current_tab.url, page_state.to_string())
        except Exception as e:
            logger.debug("[browser_task] Failed to capture page state for loop detection: %s", e)

    agent_loop = AgentLoop(
        llm=llm,
        registry=registry,
        max_iterations=MAX_ITERATIONS,
        name="browser_task",
        before_call=before_call,
        after_tool=after_tool,
        loop_guard=loop_guard,
    )

    history = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=task),
    ]

    try:
        result = (await agent_loop.run(history)).content
    except Exception as e:
        logger.error("browser_task failed: %s", e, exc_info=True)
        return ToolResult.error_result(f"browser_task failed: {type(e).__name__}: {e}")
    finally:
        if owns_browser and not keep_open:
            try:
                await browser.close()
            except Exception:
                pass

    return ToolResult.success_result(result)
