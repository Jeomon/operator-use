"""Local agents tool — call other configured Operator agents in-process."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional, Literal

from pydantic import BaseModel, Field

from operator_use.bus.views import IncomingMessage, TextPart
from operator_use.messages import HumanMessage
from operator_use.tools import Tool, ToolResult
from operator_use.agent.context.service import PromptMode

LOCAL_AGENT_DELEGATION_CHAIN = "_local_agent_delegation_chain"

logger = logging.getLogger(__name__)


class LocalAgents(BaseModel):
    action: Literal["agents", "run"] = Field(
        description=(
            "agents — list all configured local agents available for delegation. "
            "run — send a scoped task to another local agent and wait for its final answer."
        )
    )
    name: Optional[str] = Field(
        default=None,
        description="Target local agent ID to delegate to (required for action='run').",
    )
    task: Optional[str] = Field(
        default=None,
        description="Delegated task for the target local agent (required for action='run').",
    )
    detached: bool = Field(
        default=False,
        description=(
            "If True, run the agent in the background and return immediately. "
            "The result will be delivered back to this conversation automatically when done. "
            "END YOUR TURN after calling with detached=True — do not poll or wait. "
            "If False (default), block until the agent finishes and return its result directly."
        ),
    )


def _agent_capabilities(agent) -> str:
    caps: list[str] = []
    if agent.get_plugin("browser_use") is not None:
        caps.append("browser")
    if agent.get_plugin("computer_use") is not None:
        caps.append("computer")
    return ", ".join(caps) if caps else "general"


def _delegation_context(from_agent: str, to_agent: str) -> str:
    return (
        f"You are agent '{to_agent}', acting as a worker delegated a task by agent '{from_agent}'.\n"
        "Complete the task and return your findings clearly.\n"
        "Do not send messages to the user — your response goes back to the delegating agent."
    )


def _delegation_chain_from_metadata(metadata: dict[str, Any] | None) -> list[str]:
    if not isinstance(metadata, dict):
        return []

    chain = metadata.get(LOCAL_AGENT_DELEGATION_CHAIN, [])
    if not isinstance(chain, list):
        return []

    return [agent_id for agent_id in chain if isinstance(agent_id, str) and agent_id]


async def _run_detached(
    target,
    message: HumanMessage,
    session_id: str,
    incoming: IncomingMessage,
    agent_name: str,
    task_id: str,
    bus,
    reply_channel: str,
    reply_chat_id: str,
    reply_account_id: str,
    delegating_agent_id: str = "",
) -> None:
    """Run a local agent in the background and announce the result via the bus."""
    logger.info(f"[{task_id}] detached local agent '{agent_name}' started")
    extra = _delegation_context(delegating_agent_id, agent_name)
    try:
        response = await target.run(
            message=message,
            session_id=session_id,
            incoming=incoming,
            publish_stream=None,
            pending_replies=None,
            prompt_mode=PromptMode.MINIMAL,
            extra_system_prompt=extra,
        )
        result = str(response.content or "")
        status = "completed"
    except asyncio.CancelledError:
        logger.info(f"[{task_id}] detached local agent '{agent_name}' cancelled")
        return
    except Exception as e:
        logger.error(f"[{task_id}] detached local agent '{agent_name}' failed: {e}", exc_info=True)
        result = f"(error: {type(e).__name__}: {e})"
        status = "failed"

    logger.info(f"[{task_id}] detached local agent '{agent_name}' done — status={status}")

    content = (
        f"[localagent:{task_id}] Agent '{agent_name}' has finished.\n\n"
        f"Result:\n{result}\n\n"
        f"Relay this result naturally in context. Do not mention task IDs or 'localagent'."
    )
    await bus.publish_incoming(IncomingMessage(
        channel=reply_channel,
        chat_id=reply_chat_id,
        account_id=reply_account_id,
        parts=[TextPart(content=content)],
        user_id="localagent",
        metadata={"_localagent_result": True, "task_id": task_id, "from_agent": agent_name},
    ))


@Tool(
    name="localagents",
    description=(
        "Call other configured local Operator agents in-process. "
        "Useful for a manager agent coordinating specialized agents on one request. "
        "Use detached=True to run an agent in the background — result is delivered automatically."
    ),
    model=LocalAgents,
)
async def localagents(
    action: str,
    name: str | None = None,
    task: str | None = None,
    detached: bool = False,
    **kwargs,
) -> ToolResult:
    registry: dict = kwargs.get("_agent_registry") or {}
    current_agent = kwargs.get("_agent")
    current_agent_id = kwargs.get("_agent_id", "")
    current_metadata = kwargs.get("_metadata") or {}
    parent_session_id = kwargs.get("_session_id", "delegation")
    parent_channel = kwargs.get("_channel") or "direct"
    parent_chat_id = kwargs.get("_chat_id") or parent_session_id
    parent_account_id = kwargs.get("_account_id") or current_agent_id

    if action == "agents":
        if not registry:
            return ToolResult.success_result("No local agents are configured.")

        lines = ["Available local agents:"]
        for agent_id, agent in registry.items():
            marker = " (current)" if agent_id == current_agent_id else ""
            description = getattr(agent, "description", "") or "No description provided."
            lines.append(
                f"  • {agent_id}{marker} — {description} "
                f"[capabilities: {_agent_capabilities(agent)}]"
            )
        return ToolResult.success_result("\n".join(lines))

    if action != "run":
        return ToolResult.error_result(f"Unknown action '{action}'")

    if not name:
        return ToolResult.error_result("name is required for action='run'")
    if not task:
        return ToolResult.error_result("task is required for action='run'")

    target = registry.get(name)
    if target is None:
        available = ", ".join(registry.keys()) if registry else "none"
        return ToolResult.error_result(f"Unknown local agent '{name}'. Available: {available}.")

    if current_agent is not None and target is current_agent:
        return ToolResult.error_result("Refusing to delegate to the current agent. Choose a different local agent.")

    delegation_chain = _delegation_chain_from_metadata(current_metadata)
    if current_agent_id and (not delegation_chain or delegation_chain[-1] != current_agent_id):
        delegation_chain = [*delegation_chain, current_agent_id]
    if name in delegation_chain:
        chain_text = " -> ".join([*delegation_chain, name])
        return ToolResult.error_result(
            f"Refusing circular local delegation: {chain_text}. Choose a target outside the current delegation chain."
        )

    delegated_session_id = f"{parent_session_id}__delegate__{current_agent_id or 'agent'}-to-{name}"
    delegated_metadata = {
        **current_metadata,
        "_delegated_local_agent_call": True,
        "from_agent": current_agent_id,
        "to_agent": name,
        LOCAL_AGENT_DELEGATION_CHAIN: [*delegation_chain, name],
    }
    incoming = IncomingMessage(
        channel=parent_channel,
        chat_id=parent_chat_id,
        account_id=name,
        user_id=current_agent_id or "agent",
        parts=[TextPart(content=task)],
        metadata=delegated_metadata,
    )
    message = HumanMessage(content=task, metadata=incoming.metadata)

    if detached:
        bus = kwargs.get("_bus")
        if bus is None:
            return ToolResult.error_result("Bus not available for detached mode (internal error).")

        import uuid
        task_id = f"local_{name}_{uuid.uuid4().hex[:8]}"

        asyncio.create_task(
            _run_detached(
                target=target,
                message=message,
                session_id=delegated_session_id,
                incoming=incoming,
                agent_name=name,
                task_id=task_id,
                bus=bus,
                reply_channel=parent_channel,
                reply_chat_id=parent_chat_id,
                reply_account_id=parent_account_id,
                delegating_agent_id=current_agent_id,
            ),
            name=f"localagent-{task_id}",
        )
        return ToolResult.success_result(
            f"Agent '{name}' started in background (task_id={task_id}).\n"
            f"Result will be delivered automatically when done.\n"
            f"END YOUR TURN. Inform the user and stop."
        )

    response = await target.run(
        message=message,
        session_id=delegated_session_id,
        incoming=incoming,
        publish_stream=None,
        pending_replies=None,
        prompt_mode=PromptMode.MINIMAL,
        extra_system_prompt=_delegation_context(current_agent_id, name),
    )
    return ToolResult.success_result(str(response.content or ""))
