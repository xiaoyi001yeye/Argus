from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class LogSource:
    id: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LogFile:
    name: str
    size_bytes: int
    modified_at_ns: int
    kind: str
    archive_status: str = "not_archive"
    archive_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> LogFile:
        return cls(
            name=str(raw["name"]),
            size_bytes=int(raw["size_bytes"]),
            modified_at_ns=int(raw["modified_at_ns"]),
            kind=str(raw["kind"]),
            archive_status=str(raw.get("archive_status", "not_archive")),
            archive_error=raw.get("archive_error"),
        )

    def same_version_as(self, other: LogFile) -> bool:
        return (
            self.name == other.name
            and self.size_bytes == other.size_bytes
            and self.modified_at_ns == other.modified_at_ns
        )


@dataclass(frozen=True, slots=True)
class LogMatch:
    timestamp: str | None
    level: str | None
    message: str
    source: str
    cursor: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ContextLine:
    cursor: str
    message: str
    is_match: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
