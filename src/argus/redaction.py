from __future__ import annotations

import re

_PATTERNS = (
    re.compile(r"(?i)\b(password|passwd|pwd)\s*[:=]\s*\S+"),
    re.compile(r"(?i)\b(api[_-]?key|token)\s*[:=]\s*\S+"),
    re.compile(r"(?i)\b(authorization)\s*:\s*(?:bearer|basic)\s+\S+"),
)


def redact(text: str) -> str:
    result = text
    for pattern in _PATTERNS:
        result = pattern.sub(lambda match: f"{match.group(1)}=[REDACTED]", result)
    return result
