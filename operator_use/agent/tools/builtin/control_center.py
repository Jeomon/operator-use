"""Control Center tool: toggle computer_use / browser_use and restart."""

import asyncio
import json
import logging
import os
import sys
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from operator_use.paths import get_userdata_dir
from operator_use.tools import Tool, ToolResult

logger = logging.getLogger(__name__)

CONFIG_PATH = get_userdata_dir() / "config.json"
RESTART_FILE = get_userdata_dir() / "restart.json"


class ControlCenter(BaseModel):
    computer_use: Optional[bool] = Field(
        default=None,
        description="Enable or disable computer_use (Windows GUI automation). Cannot be true when browser_use is true.",
    )
    browser_use: Optional[bool] = Field(
        default=None,
        description="Enable or disable browser_use (Chrome DevTools automation). Cannot be true when computer_use is true.",
    )
    restart: bool = Field(
        default=False,
        description=(
            "Restart Operator after applying changes to reload the config. "
            "Also use this alone (no other args) to restart without changing any settings."
        ),
    )
    continue_with: Optional[str] = Field(
        default=None,
        description=(
            "Set when restart=true and there is more work to do after rebooting. "
            "Describe exactly what to continue — e.g. 'Test the new tool I just added'. "
            "Omit when restart is the final action."
        ),
    )
    agent_id: Optional[str] = Field(
        default=None,
        description="Target agent ID. Defaults to the first agent in config.",
    )

    @model_validator(mode="after")
    def check_exclusive(self) -> "ControlCenter":
        if self.computer_use and self.browser_use:
            raise ValueError("computer_use and browser_use cannot both be true.")
        return self


def _load_config_raw() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_config_raw(data: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _get_agent_entry(data: dict, agent_id: Optional[str]) -> tuple[dict, int] | tuple[None, None]:
    agents_list: list = data.get("agents", {}).get("list", [])
    if not agents_list:
        return None, None
    if agent_id is None:
        return agents_list[0], 0
    for i, entry in enumerate(agents_list):
        if entry.get("id") == agent_id:
            return entry, i
    return None, None


async def _do_restart():
    os.system("cls" if os.name == "nt" else "clear")
    frames = ["↑", "↗", "→", "↘", "↓", "↙", "←", "↖"]
    for i in range(20):
        sys.stdout.write(f"\r {frames[i % len(frames)]}  Restarting Operator...")
        sys.stdout.flush()
        await asyncio.sleep(0.5)
    sys.stdout.write("\n")
    sys.stdout.flush()
    os._exit(75)


@Tool(
    name="control_center",
    description=(
        "Control Center for Operator capabilities.\n\n"
        "Dynamically toggle computer_use (GUI automation) and browser_use (Browser automation via CDP)."
        "They are mutually exclusive — enabling one "
        "immediately disables the other, registers the relevant tools into the agent, "
        "and connects the state (desktop or browser) into the LLM context. "
        "No restart needed for capability toggles.\n\n"
        "- computer_use=true  → enable desktop automation tools + desktop state in context\n"
        "- browser_use=true   → enable browser tools + browser state in context\n"
        "- computer_use=false / browser_use=false → disable and remove from context\n"
        "- restart=true       → restart Operator (use for code/config changes)\n"
        "- Call with no arguments to get current status."
    ),
    model=ControlCenter,
)
async def control_center(
    computer_use: Optional[bool] = None,
    browser_use: Optional[bool] = None,
    restart: bool = False,
    continue_with: Optional[str] = None,
    agent_id: Optional[str] = None,
    **kwargs,
) -> ToolResult:
    data = _load_config_raw()
    agents_block = data.setdefault("agents", {})
    agents_list: list = agents_block.setdefault("list", [])

    entry, idx = _get_agent_entry(data, agent_id)
    if entry is None:
        return ToolResult.error_result("No agents found in config.json. Run 'operator onboard' first.")

    # Normalise stored keys to camelCase
    for old, new in [("computer_use", "computerUse"), ("browser_use", "browserUse")]:
        if old in entry and new not in entry:
            entry[new] = entry.pop(old)

    agent = kwargs.get("_agent")

    changes = []
    if computer_use is not None:
        entry["computerUse"] = computer_use
        if computer_use:
            entry["browserUse"] = False
            changes.append("computer_use=true, browser_use=false")
            if agent is not None:
                await agent.enable_computer_use()
        else:
            changes.append("computer_use=false")
            if agent is not None:
                await agent.disable_computer_use()

    if browser_use is not None:
        entry["browserUse"] = browser_use
        if browser_use:
            entry["computerUse"] = False
            changes.append("browser_use=true, computer_use=false")
            if agent is not None:
                await agent.enable_browser_use()
        else:
            changes.append("browser_use=false")
            if agent is not None:
                await agent.disable_browser_use()

    agents_list[idx] = entry
    _save_config_raw(data)

    cu = entry.get("computerUse", False)
    bu = entry.get("browserUse", True)
    status = (
        f"Agent: {entry.get('id', '?')}\n"
        f"  computer_use : {cu}\n"
        f"  browser_use  : {bu}"
    )

    if changes:
        msg = f"Updated — {', '.join(changes)}.\n{status}"
    else:
        msg = status

    if restart:
        if continue_with:
            channel = kwargs.get("_channel")
            chat_id = kwargs.get("_chat_id")
            account_id = kwargs.get("_account_id", "")
            restart_data = {"task": continue_with, "channel": channel, "chat_id": chat_id, "account_id": account_id}
            try:
                RESTART_FILE.parent.mkdir(parents=True, exist_ok=True)
                RESTART_FILE.write_text(json.dumps(restart_data), encoding="utf-8")
                logger.info(f"Saved continuation → {RESTART_FILE}")
            except Exception as e:
                return ToolResult.error_result(f"Could not save restart continuation: {e}")
            msg += f"\nWill continue after restart: {continue_with[:100]}"
        asyncio.ensure_future(_do_restart())
        return ToolResult.success_result(f"{msg}\nRestart initiated.", metadata={"stop_loop": True})

    return ToolResult.success_result(msg)
