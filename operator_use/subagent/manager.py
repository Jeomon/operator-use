"""SubagentManager - registry for spawning, tracking, and cancelling subagents."""

import asyncio
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from operator_use.bus import Bus
from operator_use.subagent.views import SubagentRecord

if TYPE_CHECKING:
    from operator_use.providers.base import BaseChatLLM


class SubagentManager:
    """Registry that spawns isolated subagent tasks and tracks their lifecycle."""

    def __init__(self, llm: "BaseChatLLM", bus: Bus) -> None:
        from operator_use.subagent.service import Subagent

        self._runner = Subagent(llm=llm, bus=bus)
        self._tasks: dict[str, asyncio.Task] = {}
        self._session_tasks: dict[str, set[str]] = {}
        self._records: dict[str, SubagentRecord] = {}

    async def ainvoke(self, task: str, label: str | None, channel: str, chat_id: str, account_id: str = "") -> str:
        """Spawn a background subagent. Returns task_id immediately."""
        task_id = f"sub_{uuid.uuid4().hex[:8]}"
        session_key = f"{channel}:{chat_id}"
        display_label = label or task[:50]

        record = SubagentRecord(
            task_id=task_id,
            label=display_label,
            task=task,
            channel=channel,
            chat_id=chat_id,
            account_id=account_id,
            status="running",
            started_at=datetime.now(),
        )
        self._records[task_id] = record

        t = asyncio.create_task(
            self._runner.run(record),
            name=f"subagent-{task_id}",
        )
        self._tasks[task_id] = t
        self._session_tasks.setdefault(session_key, set()).add(task_id)
        t.add_done_callback(lambda _: self._cleanup(task_id, session_key))
        return task_id

    def cancel(self, task_id: str) -> bool:
        """Cancel a running subagent. Returns True if it was running."""
        t = self._tasks.get(task_id)
        if t and not t.done():
            t.cancel()
            return True
        return False

    def cancel_by_session(self, session_key: str) -> int:
        """Cancel all running subagents for a session. Returns count cancelled."""
        count = 0
        for task_id in list(self._session_tasks.get(session_key, [])):
            if self.cancel(task_id):
                count += 1
        return count

    def get_record(self, task_id: str) -> SubagentRecord | None:
        """Return a single record by task_id."""
        return self._records.get(task_id)

    def list_all(self) -> list[SubagentRecord]:
        """Return all records (running + finished), newest first."""
        return sorted(self._records.values(), key=lambda r: r.started_at, reverse=True)

    def _cleanup(self, task_id: str, session_key: str) -> None:
        """Remove from active tracking - record stays in history."""
        self._tasks.pop(task_id, None)
        s = self._session_tasks.get(session_key)
        if s:
            s.discard(task_id)

