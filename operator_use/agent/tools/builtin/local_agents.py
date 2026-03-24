"""Local agents tool — call other configured Operator agents in-process."""

from __future__ import annotations

from typing import Optional, Literal

from pydantic import BaseModel, Field

from operator_use.bus.views import IncomingMessage, TextPart
from operator_use.messages import HumanMessage
from operator_use.tools import Tool, ToolResult


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


def _agent_capabilities(agent) -> str:
    caps: list[str] = []
    if agent.get_plugin("browser_use") is not None:
        caps.append("browser")
    if agent.get_plugin("computer_use") is not None:
        caps.append("computer")
    return ", ".join(caps) if caps else "general"


@Tool(
    name="localagents",
    description=(
        "Call other configured local Operator agents in-process. "
        "Useful for a manager agent coordinating specialized agents on one request."
    ),
    model=LocalAgents,
)
async def localagents(
    action: str,
    name: str | None = None,
    task: str | None = None,
    **kwargs,
) -> ToolResult:
    registry: dict = kwargs.get("_agent_registry") or {}
    current_agent = kwargs.get("_agent")
    current_agent_id = kwargs.get("_agent_id", "")
    parent_session_id = kwargs.get("_session_id", "delegation")

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

    delegated_session_id = f"{parent_session_id}__delegate__{current_agent_id or 'agent'}-to-{name}"
    incoming = IncomingMessage(
        channel="direct",
        chat_id=delegated_session_id,
        account_id=name,
        user_id=current_agent_id or "agent",
        parts=[TextPart(content=task)],
        metadata={
            "_delegated_local_agent_call": True,
            "from_agent": current_agent_id,
            "to_agent": name,
        },
    )

    response = await target.run(
        message=HumanMessage(content=task, metadata=incoming.metadata),
        session_id=delegated_session_id,
        incoming=incoming,
        publish_stream=None,
        pending_replies=None,
    )
    return ToolResult.success_result(str(response.content or ""))
