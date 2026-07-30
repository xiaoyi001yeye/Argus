from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from argus.models import LogFile


@dataclass(frozen=True, slots=True)
class CacheSnapshot:
    key: str
    refreshed_at: str
    files: list[LogFile]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "refreshed_at": self.refreshed_at,
            "file_count": len(self.files),
        }


class LogFileCache:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def load(self, environment: str, source_id: str) -> CacheSnapshot | None:
        path = self._entry_path(environment, source_id)
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            files = [LogFile.from_dict(file) for file in raw["files"]]
            return CacheSnapshot(
                key=str(raw["key"]),
                refreshed_at=str(raw["refreshed_at"]),
                files=files,
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid log file cache entry: {path.name}") from exc

    def refresh(
        self,
        environment: str,
        source_id: str,
        files: list[LogFile],
    ) -> CacheSnapshot:
        self._directory.mkdir(parents=True, exist_ok=True)
        snapshot = CacheSnapshot(
            key=f"{environment}/{source_id}",
            refreshed_at=datetime.now(UTC).isoformat(),
            files=files,
        )
        path = self._entry_path(environment, source_id)
        content = json.dumps(
            {
                "version": 1,
                "key": snapshot.key,
                "refreshed_at": snapshot.refreshed_at,
                "files": [file.to_dict() for file in files],
            },
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self._directory,
            prefix=f".{path.stem}-",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(content)
            temporary_path = Path(temporary.name)
        try:
            temporary_path.replace(path)
        finally:
            temporary_path.unlink(missing_ok=True)
        return snapshot

    def _entry_path(self, environment: str, source_id: str) -> Path:
        key = f"{environment}\0{source_id}".encode()
        digest = hashlib.sha256(key).hexdigest()
        return self._directory / f"{digest}.json"
