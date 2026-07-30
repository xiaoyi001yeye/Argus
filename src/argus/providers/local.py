from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile, ZipFile, is_zipfile

from argus.config import SourceConfig
from argus.models import LogFile
from argus.providers.base import LogReadError, is_safe_file_name, resolve_log_source


class LocalFileProvider:
    def __init__(
        self,
        sources: dict[str, SourceConfig],
        *,
        max_file_bytes: int = 10_000_000,
        max_extract_bytes: int = 100_000_000,
    ) -> None:
        self._sources = sources
        self._max_file_bytes = max_file_bytes
        self._max_extract_bytes = max_extract_bytes

    def read_lines(self, source_id: str) -> list[str]:
        source = resolve_log_source(self._sources, source_id)

        path = Path(source.path)
        if not path.is_file():
            raise LogReadError(f"Configured log source is unavailable: {source_id}")
        if path.stat().st_size > self._max_file_bytes:
            raise LogReadError(f"Configured log source exceeds the read limit: {source_id}")

        return path.read_text(encoding="utf-8", errors="replace").splitlines()

    def list_files(self, source_id: str) -> list[LogFile]:
        source = resolve_log_source(self._sources, source_id)

        path = Path(source.path)
        if path.is_file():
            return [_describe_file(path, self._max_extract_bytes)]
        if path.is_dir():
            return [
                _describe_file(file, self._max_extract_bytes)
                for file in sorted(path.iterdir())
                if file.is_file()
            ]
        raise LogReadError(f"Configured log source is unavailable: {source_id}")

    def extract_archives(self, source_id: str, archive_names: list[str]) -> list[str]:
        source = resolve_log_source(self._sources, source_id)
        source_path = Path(source.path)
        directory = source_path if source_path.is_dir() else source_path.parent
        archives = []
        for archive_name in archive_names:
            if not is_safe_file_name(archive_name) or not archive_name.lower().endswith(".zip"):
                raise LogReadError(f"Unsafe ZIP archive name: {archive_name}")
            archive = directory / archive_name
            if not archive.is_file() or not is_zipfile(archive):
                raise LogReadError(f"ZIP archive is unavailable or invalid: {archive_name}")
            archives.append(archive)

        for archive in archives:
            try:
                with ZipFile(archive) as zip_file:
                    _validate_zip_members(zip_file, archive.name, self._max_extract_bytes)
                    zip_file.extractall(directory)
            except BadZipFile as exc:
                raise LogReadError(f"ZIP archive is invalid: {archive.name}") from exc
        return [archive.name for archive in archives]


def _describe_file(path: Path, max_extract_bytes: int) -> LogFile:
    stat = path.stat()
    kind = _file_kind(path.name)
    archive_status = "not_archive"
    archive_error = None
    if kind == "zip":
        if not is_zipfile(path):
            archive_status = "unavailable"
            archive_error = "invalid_zip"
        else:
            try:
                with ZipFile(path) as zip_file:
                    _validate_zip_members(zip_file, path.name, max_extract_bytes)
                archive_status = "extractable"
            except BadZipFile:
                archive_status = "unavailable"
                archive_error = "invalid_zip"
            except LogReadError as exc:
                archive_status = "unavailable"
                archive_error = (
                    "archive_too_large" if "extraction limit" in str(exc) else "unsafe_archive"
                )
    return LogFile(
        name=path.name,
        size_bytes=stat.st_size,
        modified_at_ns=stat.st_mtime_ns,
        kind=kind,
        archive_status=archive_status,
        archive_error=archive_error,
    )


def _file_kind(file_name: str) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".log":
        return "log"
    if suffix == ".zip":
        return "zip"
    return "other"


def _validate_zip_members(
    zip_file: ZipFile,
    archive_name: str,
    max_extract_bytes: int,
) -> None:
    total_size = 0
    for member in zip_file.infolist():
        total_size += member.file_size
        if total_size > max_extract_bytes:
            raise LogReadError(f"ZIP archive exceeds the extraction limit: {archive_name}")
        member_path = Path(member.filename)
        if member_path.is_absolute() or ".." in member_path.parts:
            raise LogReadError(f"ZIP archive contains an unsafe path: {archive_name}")
        file_type = member.external_attr >> 16
        if file_type & 0o170000 == 0o120000:
            raise LogReadError(f"ZIP archive contains a symbolic link: {archive_name}")
