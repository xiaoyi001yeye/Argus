from __future__ import annotations

from argus.config import SourceConfig


class SshLogProvider:
    """Boundary for milestone two; intentionally performs no SSH operations yet."""

    def __init__(self, ssh_alias: str, sources: dict[str, SourceConfig]) -> None:
        self._ssh_alias = ssh_alias
        self._sources = sources

    def read_lines(self, source_id: str) -> list[str]:
        raise NotImplementedError(
            "SSH reading is not enabled in the MVP. Use the local provider fixture first."
        )
