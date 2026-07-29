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
