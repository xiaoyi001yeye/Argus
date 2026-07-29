from __future__ import annotations

from typing import Protocol


class LogProvider(Protocol):
    def read_lines(self, source_id: str) -> list[str]:
        """Return bounded lines for an allow-listed source."""
