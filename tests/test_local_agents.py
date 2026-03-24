from unittest.mock import AsyncMock, MagicMock

import pytest

from operator_use.agent.tools.governance import GovernanceProfile
from operator_use.agent.tools.builtin.local_agents import localagents
from operator_use.messages.service import AIMessage


def make_target_agent(response_text: str = "delegated result", description: str = "Research specialist"):
    agent = MagicMock()
    agent.description = description
    agent.get_plugin.side_effect = lambda name: None
    agent.run = AsyncMock(return_value=AIMessage(content=response_text))
    return agent


@pytest.mark.asyncio
async def test_localagents_lists_available_agents():
    current = make_target_agent(description="Manager")
    target = make_target_agent(description="Browser specialist")

    result = await localagents.ainvoke(
        action="agents",
        _agent=current,
        _agent_id="manager",
        _agent_registry={"manager": current, "browser": target},
    )

    assert result.success is True
    assert result.output is not None
    assert "manager (current)" in result.output
    assert "Browser specialist" in result.output
    assert "[capabilities:" not in result.output


@pytest.mark.asyncio
async def test_localagents_runs_target_agent():
    current = make_target_agent(description="Manager")
    target = make_target_agent(response_text="done", description="Writer")

    result = await localagents.ainvoke(
        action="run",
        name="writer",
        task="Draft a summary",
        _agent=current,
        _agent_id="manager",
        _session_id="chat:42",
        _agent_registry={"manager": current, "writer": target},
    )

    assert result.success is True
    assert result.output == "done"
    target.run.assert_awaited_once()


@pytest.mark.asyncio
async def test_localagents_refuses_self_delegation():
    current = make_target_agent(description="Manager")

    result = await localagents.ainvoke(
        action="run",
        name="manager",
        task="Do it yourself",
        _agent=current,
        _agent_id="manager",
        _agent_registry={"manager": current},
    )

    assert result.success is False
    assert result.error is not None
    assert "Refusing to delegate" in result.error


@pytest.mark.asyncio
async def test_localagents_passes_governance_profile_to_target():
    current = make_target_agent(description="Manager")
    target = make_target_agent(response_text="done", description="Writer")

    result = await localagents.ainvoke(
        action="run",
        name="writer",
        task="Draft a summary",
        allowed_tools=["web.*"],
        _agent=current,
        _agent_id="manager",
        _session_id="chat:42",
        _agent_registry={"manager": current, "writer": target},
    )

    assert result.success is True
    incoming = target.run.await_args.kwargs["incoming"]
    profile = incoming.metadata["_governance_profile"]
    assert profile["allowed_tools"] == ["web.*"]
    assert "parent" not in profile
