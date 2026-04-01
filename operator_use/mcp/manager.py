"""MCP Manager — handles MCP server connection lifecycle."""

import logging
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Any

from operator_use.mcp.tool import MCPTool

if TYPE_CHECKING:
    from operator_use.config.service import MCPServerConfig
    from mcp import ClientSession

logger = logging.getLogger(__name__)


class MCPManager:
    """Manages MCP server connections and tool lifecycle."""

    def __init__(self, server_configs: "list[MCPServerConfig]"):
        # Map server_name -> MCPServerConfig
        self._configs: dict[str, "MCPServerConfig"] = {c.name: c for c in server_configs}
        # Map server_name -> AsyncExitStack (keeps context managers alive)
        self._stacks: dict[str, AsyncExitStack] = {}
        # Map server_name -> list[MCPTool] (tools registered for that connection)
        self._tools: dict[str, list[MCPTool]] = {}

    def is_connected(self, server_name: str) -> bool:
        """Check if a server is currently connected."""
        return server_name in self._stacks

    def list_servers(self) -> list[dict]:
        """Return status info for all configured servers."""
        result = []
        for name, cfg in self._configs.items():
            result.append({
                "name": name,
                "transport": cfg.transport,
                "connected": self.is_connected(name),
                "tool_count": len(self._tools.get(name, [])),
            })
        return result

    async def connect(self, server_name: str) -> list[MCPTool]:
        """Connect to an MCP server and return its tools as MCPTool instances."""
        if server_name in self._stacks:
            raise ValueError(f"Server '{server_name}' is already connected")

        cfg = self._configs.get(server_name)
        if cfg is None:
            raise ValueError(f"No MCP server config found for '{server_name}'")

        stack = AsyncExitStack()
        try:
            session = await self._open_session(stack, cfg)
            await session.initialize()
            tools_result = await session.list_tools()
        except Exception:
            await stack.aclose()
            raise

        mcp_tools = [
            MCPTool(
                server_name=server_name,
                mcp_tool_name=t.name,
                description=t.description or "",
                input_schema=t.inputSchema,
                session=session,
            )
            for t in tools_result.tools
        ]

        self._stacks[server_name] = stack
        self._tools[server_name] = mcp_tools
        logger.info(f"MCP connected | server={server_name} tools={len(mcp_tools)}")
        return mcp_tools

    async def disconnect(self, server_name: str) -> list[str]:
        """Disconnect from an MCP server. Returns list of registered tool names."""
        if server_name not in self._stacks:
            raise ValueError(f"Server '{server_name}' is not connected")

        tool_names = [t.name for t in self._tools.get(server_name, [])]

        stack = self._stacks.pop(server_name)
        self._tools.pop(server_name, None)

        try:
            await stack.aclose()
        except Exception as e:
            logger.warning(f"Error closing MCP stack for '{server_name}': {e}")

        logger.info(f"MCP disconnected | server={server_name}")
        return tool_names

    async def disconnect_all(self) -> None:
        """Gracefully disconnect all connected servers."""
        for name in list(self._stacks.keys()):
            try:
                await self.disconnect(name)
            except Exception as e:
                logger.warning(f"Error disconnecting MCP server '{name}': {e}")

    @staticmethod
    async def _open_session(stack: AsyncExitStack, cfg: "MCPServerConfig") -> "ClientSession":
        """Open the appropriate MCP transport and session, managed by stack."""
        from mcp import ClientSession

        if cfg.transport == "stdio":
            from mcp import StdioServerParameters
            from mcp.client.stdio import stdio_client

            if not cfg.command:
                raise ValueError(f"MCP server '{cfg.name}' with transport=stdio requires a command")

            params = StdioServerParameters(
                command=cfg.command,
                args=cfg.args,
                env=cfg.env or None,
            )
            read, write = await stack.enter_async_context(stdio_client(params))

        elif cfg.transport in ("http", "sse"):
            from mcp.client.streamable_http import streamablehttp_client

            if not cfg.url:
                raise ValueError(
                    f"MCP server '{cfg.name}' with transport={cfg.transport} requires a url"
                )

            headers = {}
            if cfg.auth_token:
                headers["Authorization"] = f"Bearer {cfg.auth_token}"

            read, write, _ = await stack.enter_async_context(
                streamablehttp_client(cfg.url, headers=headers)
            )

        else:
            raise ValueError(f"Unknown MCP transport '{cfg.transport}' for server '{cfg.name}'")

        session = await stack.enter_async_context(ClientSession(read, write))
        return session
