"""ACP — Agent Communication Protocol support for Operator.

Server: exposes Operator as an ACP agent (REST + SSE)
Client: calls remote ACP agents (e.g. Claude Code, Gemini CLI)
Channel: integrates the ACP server into the gateway bus

Quick start
-----------
Server (expose Operator via ACP):

    from operator_use.acp import ACPChannel, ACPServerConfig

    acp = ACPChannel(ACPServerConfig(enabled=True, port=8765), bus=bus)
    gateway.add_channel(acp)

Client (call Claude Code or another ACP agent):

    from operator_use.acp import ACPClient, ACPClientConfig

    cfg = ACPClientConfig(base_url="http://localhost:9000", agent_id="claude-code")
    async with ACPClient(cfg) as client:
        result = await client.run("add type hints to auth.py")
"""

from operator_use.acp.config import ACPClientConfig, ACPServerConfig, ACPStdioConfig
from operator_use.acp.models import (
    AgentListResponse,
    AgentMetadata,
    MessagePart,
    Run,
    RunCreateRequest,
    RunMode,
    RunStatus,
    TextMessagePart,
)
from operator_use.acp.client import ACPClient
from operator_use.acp.server import ACPServer
from operator_use.acp.channel import ACPChannel
from operator_use.acp.stdio_channel import ACPStdioChannel
from operator_use.acp.provenance import ACPProvenance

__all__ = [
    # Config
    "ACPServerConfig",
    "ACPClientConfig",
    "ACPStdioConfig",
    # Models
    "Run",
    "RunCreateRequest",
    "RunMode",
    "RunStatus",
    "MessagePart",
    "TextMessagePart",
    "AgentMetadata",
    "AgentListResponse",
    # Core classes
    "ACPServer",
    "ACPClient",
    "ACPChannel",
    "ACPStdioChannel",
    "ACPProvenance",
]
