from datetime import datetime, timedelta
from pathlib import Path


class Memory:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.memory_file = workspace / "memory" / "MEMORY.md"

    def read_memory(self) -> str:
        if not self.memory_file.exists():
            return ""
        return self.memory_file.read_text(encoding="utf-8")

    def write_memory(self, memory: str) -> None:
        self.memory_file.write_text(memory, encoding="utf-8")

    def _read_summary(self, date: str) -> str:
        path = self.workspace / "memory" / date / "summary.md"
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def get_memory_context(self) -> str | None:
        sections: list[str] = []

        long_term = self.read_memory()
        if long_term:
            sections.append(f"### Long-Term Memory\n\n{long_term}")

        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        for date, label in [(today, "Today"), (yesterday, "Yesterday")]:
            summary = self._read_summary(date)
            if summary:
                sections.append(f"### {label}'s Summary ({date})\n\n{summary}")

        if not sections:
            return None
        return "## Memory\n\n" + "\n\n---\n\n".join(sections)
