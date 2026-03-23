"""ACP channel — integrates the ACP server into the Operator gateway.

When enabled, this channel:
  1. Starts an ACP-compliant REST server that accepts runs from external ACP clients
     (e.g. Claude Code, Zed, JetBrains) and routes them through the Operator agent.
  2. Translates ACP RunCreateRequest → IncomingMessage (bus) and
     OutgoingMessage (bus) → ACP run output / SSE stream.

Config example (in your runner setup):
    from operator_use.acp.channel import ACPChannel
    from operator_use.acp.config import ACPServerConfig

    acp_channel = ACPChannel(
        ACPServerConfig(enabled=True, port=8765),
        bus=bus,
    )
    gateway.add_channel(acp_channel)
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from operator_use.acp.config import ACPServerConfig
from operator_use.acp.server import ACPServer
from operator_use.bus.views import (
    IncomingMessage,
    OutgoingMessage,
    StreamPhase,
    TextPart,
    text_from_parts,
)
from operator_use.gateway.channels.base import BaseChannel

logger = logging.getLogger(__name__)


class ACPChannel(BaseChannel):
    """ACP server as a gateway channel.

    External ACP clients send runs → converted to IncomingMessages on the bus.
    Agent responses (OutgoingMessages) → collected and surfaced back to the ACP client
    via the run output / SSE stream.
    """

    def __init__(self, config: ACPServerConfig, bus=None) -> None:
        super().__init__(config, bus)
        # Pending response queues: chat_id (== run_id) -> asyncio.Queue[str | None]
        self._response_queues: dict[str, asyncio.Queue] = {}
        self._server = ACPServer(config, self._agent_runner)

    @property
    def name(self) -> str:
        return "acp"

    # ------------------------------------------------------------------
    # BaseChannel lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if not self.config.enabled:
            logger.info("ACP channel disabled, skipping")
            return
        self.running = True
        await self._listen()

    async def stop(self) -> None:
        self.running = False
        await self._server.stop()
        # Drain all pending response queues
        for q in self._response_queues.values():
            await q.put(None)
        self._response_queues.clear()

    async def _listen(self) -> None:
        """Start the ACP HTTP server (non-blocking — runs in background)."""
        await self._server.start()

    # ------------------------------------------------------------------
    # Outgoing: agent → ACP client
    # ------------------------------------------------------------------

    async def send(self, message: OutgoingMessage) -> int | None:
        """Receive agent output and forward to the waiting ACP run queue."""
        run_id = message.chat_id
        queue = self._response_queues.get(run_id)
        if not queue:
            logger.debug(f"ACP channel: no queue for run {run_id}, dropping message")
            return None

        phase = message.stream_phase

        if phase in (StreamPhase.CHUNK, StreamPhase.END, None):
            text = text_from_parts(message.parts or [])
            if text:
                await queue.put(text)

        if phase in (StreamPhase.END, StreamPhase.DONE) or phase is None:
            # Signal end of response
            await queue.put(None)

        return None

    # ------------------------------------------------------------------
    # Agent runner callback (used by ACPServer)
    # ------------------------------------------------------------------

    async def _agent_runner(
        self, input_text: str, session_id: str | None
    ) -> AsyncIterator[str]:
        """Bridge: ACP run → IncomingMessage → bus → response chunks."""
        import uuid

        run_id = session_id or str(uuid.uuid4())
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._response_queues[run_id] = queue

        incoming = IncomingMessage(
            channel=self.name,
            chat_id=run_id,
            parts=[TextPart(content=input_text)],
            user_id=run_id,
            metadata={"acp_session_id": session_id, "run_id": run_id},
        )
        await self.receive(incoming)

        # Yield chunks until sentinel
        try:
            while True:
                chunk = await asyncio.wait_for(queue.get(), timeout=120.0)
                if chunk is None:
                    break
                yield chunk
        except asyncio.TimeoutError:
            logger.warning(f"ACP run {run_id} timed out waiting for agent response")
        finally:
            self._response_queues.pop(run_id, None)
