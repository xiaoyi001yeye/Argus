from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from argus.config import SourceConfig
from argus.models import LogFile


class LogReadError(RuntimeError):
    """Raised when an approved log source cannot be read safely."""


@dataclass(frozen=True, slots=True)
class ResolvedLogSource:
    id: str
    path: Path
    is_virtual_file: bool


class LogProvider(Protocol):
    def list_files(self, source_id: str) -> list[LogFile]:
        """Return all regular files for an allow-listed source without reading contents."""

    def extract_archives(self, source_id: str, archive_names: list[str]) -> list[str]:
        """Safely extract approved ZIP archives in place and return their names."""

    def read_lines(self, source_id: str) -> list[str]:
        """Return bounded lines for an allow-listed source."""


def resolve_log_source(
    sources: dict[str, SourceConfig],
    source_id: str,
) -> ResolvedLogSource:
    source = sources.get(source_id)
    if source is not None:
        return ResolvedLogSource(source_id, source.path, is_virtual_file=False)

    for parent_id, parent in sorted(sources.items(), key=lambda item: len(item[0]), reverse=True):
        prefix = f"{parent_id}/"
        if not source_id.startswith(prefix):
            continue
        file_name = source_id.removeprefix(prefix)
        if _is_safe_log_file_name(file_name):
            return ResolvedLogSource(source_id, parent.path / file_name, is_virtual_file=True)
        break

    raise LogReadError(f"Unknown log source: {source_id}")


def _is_safe_log_file_name(file_name: str) -> bool:
    return file_name.endswith(".log") and is_safe_file_name(file_name)


def is_safe_file_name(file_name: str) -> bool:
    path = PurePosixPath(file_name)
    return (
        path.name == file_name
        and file_name not in {"", ".", ".."}
        and not any(ord(character) < 32 for character in file_name)
    )
