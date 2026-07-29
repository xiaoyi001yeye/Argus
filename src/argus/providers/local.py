from __future__ import annotations

from pathlib import Path

from argus.config import SourceConfig


class LogReadError(RuntimeError):
    """Raised when an approved log source cannot be read safely."""


class LocalFileProvider:
    def __init__(
        self,
        sources: dict[str, SourceConfig],
        *,
        max_file_bytes: int = 10_000_000,
    ) -> None:
        self._sources = sources
        self._max_file_bytes = max_file_bytes

    def read_lines(self, source_id: str) -> list[str]:
        source = self._sources.get(source_id)
        if source is None:
            raise LogReadError(f"Unknown log source: {source_id}")

        path = Path(source.path)
        if not path.is_file():
            raise LogReadError(f"Configured log source is unavailable: {source_id}")
        if path.stat().st_size > self._max_file_bytes:
            raise LogReadError(f"Configured log source exceeds the read limit: {source_id}")

        return path.read_text(encoding="utf-8", errors="replace").splitlines()
