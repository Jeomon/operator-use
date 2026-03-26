"""SubagentRunner — isolated agent loop that executes a delegated task."""

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from operator_use.agent.tools import ToolRegistry
from operator_use.agent.tools.builtin import FILESYSTEM_TOOLS, WEB_TOOLS, TERMINAL_TOOLS
from operator_use.bus import Bus, IncomingMessage
from operator_use.bus.views import TextPart
from operator_use.messages.service import SystemMessage, HumanMessage, ToolMessage
from operator_use.providers.events import LLMEventType
from operator_use.subagent.views import SubagentRecord

if TYPE_CHECKING:
    from operator_use.providers.base import BaseChatLLM
    from operator_use.config.service import SubagentConfig

logger = logging.getLogger(__name__)

DEFAULT_MAX_ITERATIONS = 20

DEFAULT_SYSTEM_PROMPT = """You are a subagent. A task has been delegated to you by the main agent.

Complete the task using your tools (filesystem, web search, terminal).
When finished, respond with a clear summary of your findings or results.
Do not send messages to the user — your final response is relayed by the main agent."""


class Subagent:
    """Runs an isolated agent loop for a single delegated task."""

    def __init__(self, llm: "BaseChatLLM", bus: Bus, config: "SubagentConfig | None" = None) -> None:
        self.llm = llm
        self.bus = bus
        self.config = config

    async def run(self, record: SubagentRecord) -> None:
        """Execute the task and update the record with status/result when done."""
        logger.info(f"[{record.task_id}] subagent '{record.label}' started")

        from operator_use.agent.tools.builtin import resolve_tools
        if self.config and self.config.tools:
            tools_cfg = self.config.tools
            tool_list = resolve_tools(
                profile=tools_cfg.profile,
                also_allow=tools_cfg.also_allow,
                deny=tools_cfg.deny,
            )
        else:
            tool_list = FILESYSTEM_TOOLS + WEB_TOOLS + TERMINAL_TOOLS

        registry = ToolRegistry()
        registry.register_tools(tool_list)
        registry.set_extension("_llm", self.llm)

        tools = registry.list_tools()

        system_prompt = self.config.system_prompt if (self.config and self.config.system_prompt) else DEFAULT_SYSTEM_PROMPT
        max_iterations = self.config.max_iterations if self.config else DEFAULT_MAX_ITERATIONS

        history = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=record.task),
        ]

        result = "(no result)"
        try:
            for _ in range(max_iterations):
                messages = list(history)

                event = await self.llm.ainvoke(messages=messages, tools=tools)
                match event.type:
                    case LLMEventType.TOOL_CALL:
                        tc = event.tool_call
                        tr = await registry.aexecute(tc.name, tc.params)
                        history.append(ToolMessage(
                            id=tc.id,
                            name=tc.name,
                            params=tc.params,
                            content=tr.output if tr.success else tr.error,
                        ))
                    case LLMEventType.TEXT:
                        result = event.content or "(no result)"
                        break
            else:
                result = f"(hit {max_iterations}-iteration limit without finishing)"

            record.status = "completed"

        except asyncio.CancelledError:
            logger.info(f"[{record.task_id}] subagent '{record.label}' cancelled")
            record.status = "cancelled"
            record.finished_at = datetime.now()
            return

        except Exception as e:
            logger.error(f"[{record.task_id}] subagent '{record.label}' failed: {e}", exc_info=True)
            result = f"(error: {type(e).__name__}: {e})"
            record.status = "failed"

        record.result = result
        record.finished_at = datetime.now()
        logger.info(f"[{record.task_id}] subagent '{record.label}' done — status={record.status}")
        await self._announce(record)

    async def _announce(self, record: SubagentRecord) -> None:
        """Publish the result back to the origin session as an incoming message."""
        content = (
            f"[subagent:{record.task_id}] Task '{record.label}' has finished.\n\n"
            f"Result:\n{record.result}\n\n"
            f"Summarize this naturally for the user in 1-2 sentences. "
            f"Do not mention technical terms like 'subagent' or task IDs."
        )
        await self.bus.publish_incoming(IncomingMessage(
            channel=record.channel,
            chat_id=record.chat_id,
            account_id=record.account_id,
            parts=[TextPart(content=content)],
            user_id="subagent",
            metadata={"_subagent_result": True, "task_id": record.task_id},
        ))

