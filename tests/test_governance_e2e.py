"""Online E2E coverage for governance using the configured DeepSeek provider."""

import asyncio
import os

import pytest

from operator_use.agent.tools.governance import GovernanceProfile
from operator_use.bus import Bus
from operator_use.cli.start import _build_agents
from operator_use.config.service import (
    AgentDefinition,
    AgentsConfig,
    Config,
    GovernanceConfig,
    LLMConfig,
    PolicyDefinition,
    ProviderConfig,
    ProvidersConfig,
    load_config,
)
from operator_use.messages import HumanMessage, ToolMessage
from operator_use.paths import get_userdata_dir


def _deepseek_api_key() -> str:
    env_api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if env_api_key:
        return env_api_key
    config = load_config(get_userdata_dir())
    api_key = config.providers.deepseek.api_key.strip()
    if not api_key or api_key == "sk-823357d8cdc840668f56681c77bff745":
        return ""
    return api_key


def _tool_messages(agent, session_id: str) -> list[ToolMessage]:
    session = agent.sessions.get_or_create(session_id)
    return [message for message in session.messages if isinstance(message, ToolMessage)]


def _any_tool_message_contains(agent, text: str) -> bool:
    lowered = text.lower()
    for session in agent.sessions._sessions.values():
        for message in session.messages:
            if isinstance(message, ToolMessage) and lowered in (message.content or "").lower():
                return True
    return False


def _build_live_agents(tmp_path):
    api_key = _deepseek_api_key()
    if not api_key:
        pytest.skip("DeepSeek API key is not configured in ~/.operator-use/config.json")

    boss_workspace = tmp_path / "boss"
    researcher_workspace = tmp_path / "researcher"
    coder_workspace = tmp_path / "coder"
    locked_dir = coder_workspace / "locked"

    for workspace in (boss_workspace, researcher_workspace, coder_workspace, locked_dir):
        workspace.mkdir(parents=True, exist_ok=True)

    (researcher_workspace / "note.txt").write_text("RESEARCH_E2E_OK", encoding="utf-8")
    (locked_dir / "secret.txt").write_text("TOP_SECRET_E2E", encoding="utf-8")

    config = Config(
        agents=AgentsConfig(
            defaults={"maxToolIterations": 8, "streaming": False},
            list=[
                AgentDefinition(
                    id="boss",
                    description="Coordinator",
                    workspace=str(boss_workspace),
                    policy="manager",
                    llm_config=LLMConfig(provider="deepseek", model="deepseek-chat"),
                    browser_use=False,
                    computer_use=False,
                ),
                AgentDefinition(
                    id="researcher",
                    description="Reader",
                    workspace=str(researcher_workspace),
                    policy="researcher",
                    llm_config=LLMConfig(provider="deepseek", model="deepseek-chat"),
                    browser_use=False,
                    computer_use=False,
                ),
                AgentDefinition(
                    id="coder",
                    description="Terminal specialist",
                    workspace=str(coder_workspace),
                    policy="coder",
                    llm_config=LLMConfig(provider="deepseek", model="deepseek-chat"),
                    browser_use=False,
                    computer_use=False,
                ),
            ],
        ),
        policies={
            "manager": PolicyDefinition(allowed_tools=["agents.*", "message.*", "channel.send"]),
            "researcher": PolicyDefinition(allowed_tools=["filesystem.read", "filesystem.list", "message.*"]),
            "coder": PolicyDefinition(allowed_tools=["filesystem.*", "terminal.exec", "process.*", "message.*"]),
        },
        governance=GovernanceConfig(
            protect_codebase=True,
            protect_runtime_config=True,
            protected_paths=[str(locked_dir)],
        ),
        providers=ProvidersConfig(
            deepseek=ProviderConfig(api_key=api_key),
        ),
    )

    agents = _build_agents(config, cron=None, gateway=None, bus=Bus())
    return agents


async def _wait_for_subagent(subagent_store, task_id: str, timeout: float = 60.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        record = subagent_store.get_record(task_id)
        if record is not None and record.finished_at is not None:
            return record
        await asyncio.sleep(1)
    raise AssertionError(f"Timed out waiting for subagent {task_id}")


@pytest.mark.asyncio
async def test_governance_e2e_deepseek_direct_delegate_and_subagent(tmp_path):
    agents = _build_live_agents(tmp_path)
    boss = agents["boss"]
    researcher = agents["researcher"]
    coder = agents["coder"]

    boss_session_id = "e2e:boss-direct-block"
    boss_response = await boss.run(
        message=HumanMessage(
            content=(
                "Use the terminal tool to run `echo BOSS_DIRECT_GOV`. "
                "Do not delegate. After the tool result, reply with `boss-direct-complete`."
            )
        ),
        session_id=boss_session_id,
    )
    assert "boss-direct" in boss_response.content.lower()
    assert any("not allowed" in message.content.lower() for message in _tool_messages(boss, boss_session_id))

    coder_terminal_session = "e2e:coder-terminal"
    coder_terminal_response = await coder.run(
        message=HumanMessage(
            content=(
                "Use only the terminal tool. Run "
                "`echo CODER_DIRECT_E2E_OK > direct_ok.txt && type direct_ok.txt`. "
                "Then reply with exactly what the command printed."
            )
        ),
        session_id=coder_terminal_session,
    )
    assert "CODER_DIRECT_E2E_OK" in coder_terminal_response.content
    assert any("CODER_DIRECT_E2E_OK" in message.content for message in _tool_messages(coder, coder_terminal_session))

    coder_protected_session = "e2e:coder-protected"
    coder_protected_response = await coder.run(
        message=HumanMessage(
            content=(
                "Use only the read_file tool on `locked/secret.txt`. "
                "Do not use terminal. After the tool result, reply with `protected-path-complete`."
            )
        ),
        session_id=coder_protected_session,
    )
    assert "protected-path" in coder_protected_response.content.lower()
    assert any("protected path" in message.content.lower() for message in _tool_messages(coder, coder_protected_session))

    boss_delegate_coder_session = "e2e:boss-delegate-coder"
    boss_delegate_coder_response = await boss.run(
        message=HumanMessage(
            content=(
                "Use localagents to ask `coder` to use only the terminal tool and run "
                "`echo DELEGATED_CODER_E2E_OK > delegated_ok.txt && type delegated_ok.txt`. "
                "Ask it to return only the command output, then return that output to me."
            )
        ),
        session_id=boss_delegate_coder_session,
    )
    assert "DELEGATED_CODER_E2E_OK" in boss_delegate_coder_response.content
    assert _any_tool_message_contains(coder, "DELEGATED_CODER_E2E_OK")

    boss_delegate_researcher_session = "e2e:boss-delegate-researcher"
    boss_delegate_researcher_response = await boss.run(
        message=HumanMessage(
            content=(
                "Use localagents to ask `researcher` to read `note.txt` using only `filesystem.read`. "
                "Ask it to return only the file contents, then return only those contents to me."
            )
        ),
        session_id=boss_delegate_researcher_session,
    )
    assert "RESEARCH_E2E_OK" in boss_delegate_researcher_response.content
    assert _any_tool_message_contains(researcher, "RESEARCH_E2E_OK")

    subagent_task_id = await coder.subagent_store.ainvoke(
        task=(
            "Use only the read_file tool on `locked/secret.txt`. "
            "Do not use terminal. If blocked, summarize the error in one short sentence."
        ),
        label="locked-read",
        channel="test",
        chat_id="governance-e2e",
        governance_profile=GovernanceProfile(allowed_tools=["filesystem.read"]),
    )
    subagent_record = await _wait_for_subagent(coder.subagent_store, subagent_task_id)

    assert subagent_record.status == "completed"
    assert subagent_record.result is not None
    assert "protected path" in subagent_record.result.lower()
