from dataclasses import dataclass
from datetime import datetime


@dataclass
class SubagentRecord:
    task_id: str
    label: str
    task: str
    channel: str
    chat_id: str
    account_id: str
    status: str          # "running" | "completed" | "failed" | "cancelled"
    started_at: datetime
    finished_at: datetime | None = None
    result: str | None = None
