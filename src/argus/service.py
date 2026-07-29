from __future__ import annotations

import re
from datetime import datetime

from argus.config import EnvironmentConfig
from argus.models import ContextLine, LogMatch, LogSource
from argus.providers.base import LogProvider
from argus.redaction import redact

_PREFIX = re.compile(
    r"^(?P<timestamp>\S+)\s+(?P<level>TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL)\s+(?P<message>.*)$",
    re.IGNORECASE,
)


class LogService:
    def __init__(
        self,
        environment: EnvironmentConfig,
        provider: LogProvider,
        *,
        max_results: int = 200,
        max_context_lines: int = 100,
        max_line_length: int = 4_000,
    ) -> None:
        self._environment = environment
        self._provider = provider
        self._max_results = max_results
        self._max_context_lines = max_context_lines
        self._max_line_length = max_line_length

    def list_sources(self) -> list[LogSource]:
        return [
            LogSource(id=source_id, description=source.description)
            for source_id, source in sorted(self._environment.sources.items())
        ]

    def search(
        self,
        source_id: str,
        query: str,
        *,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 100,
    ) -> tuple[list[LogMatch], bool]:
        terms = [term.strip().casefold() for term in re.split(r"\s+OR\s+", query, flags=re.I)]
        terms = [term for term in terms if term]
        if not terms:
            raise ValueError("query must contain at least one term")

        start = _parse_bound(start_time)
        end = _parse_bound(end_time)
        if start and end and start > end:
            raise ValueError("start_time must not be later than end_time")

        bounded_limit = max(1, min(limit, self._max_results))
        matches: list[LogMatch] = []
        truncated = False
        for line_number, raw_line in enumerate(self._provider.read_lines(source_id), start=1):
            parsed = _parse_line(raw_line)
            timestamp = _try_parse_timestamp(parsed["timestamp"])
            if start and (timestamp is None or timestamp < start):
                continue
            if end and (timestamp is None or timestamp > end):
                continue
            if not any(term in raw_line.casefold() for term in terms):
                continue
            if len(matches) >= bounded_limit:
                truncated = True
                break
            matches.append(
                LogMatch(
                    timestamp=parsed["timestamp"],
                    level=parsed["level"],
                    message=self._safe_line(parsed["message"]),
                    source=source_id,
                    cursor=_cursor(source_id, line_number),
                )
            )
        return matches, truncated

    def context(
        self,
        source_id: str,
        cursor: str,
        *,
        before: int = 10,
        after: int = 10,
    ) -> list[ContextLine]:
        match_line = _decode_cursor(source_id, cursor)
        before = max(0, min(before, self._max_context_lines))
        after = max(0, min(after, self._max_context_lines))
        lines = self._provider.read_lines(source_id)
        if match_line > len(lines):
            raise ValueError("cursor no longer exists in the source")

        start = max(1, match_line - before)
        end = min(len(lines), match_line + after)
        return [
            ContextLine(
                cursor=_cursor(source_id, line_number),
                message=self._safe_line(lines[line_number - 1]),
                is_match=line_number == match_line,
            )
            for line_number in range(start, end + 1)
        ]

    def _safe_line(self, line: str) -> str:
        return redact(line[: self._max_line_length])


def _parse_line(line: str) -> dict[str, str | None]:
    match = _PREFIX.match(line)
    if not match:
        return {"timestamp": None, "level": None, "message": line}
    return match.groupdict()


def _parse_bound(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid ISO-8601 time: {value}") from exc


def _try_parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _cursor(source_id: str, line_number: int) -> str:
    return f"{source_id}:{line_number}"


def _decode_cursor(source_id: str, cursor: str) -> int:
    prefix = f"{source_id}:"
    if not cursor.startswith(prefix):
        raise ValueError("cursor does not belong to this source")
    try:
        line_number = int(cursor.removeprefix(prefix))
    except ValueError as exc:
        raise ValueError("invalid cursor") from exc
    if line_number < 1:
        raise ValueError("invalid cursor")
    return line_number
