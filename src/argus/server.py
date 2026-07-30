from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from argus.cache import LogFileCache
from argus.config import EnvironmentConfig, load_config
from argus.providers.local import LocalFileProvider
from argus.providers.ssh import SshLogProvider
from argus.service import LogService

mcp = FastMCP("Argus")


def _config_path() -> Path:
    return Path(os.environ.get("ARGUS_CONFIG", "config/environments.yaml")).resolve()


def _cache_directory() -> Path:
    configured = os.environ.get("ARGUS_CACHE_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    cache_home = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache_home / "argus" / "log-files"


def _service(environment: str) -> LogService:
    config = load_config(_config_path())
    selected = config.environments.get(environment)
    if selected is None:
        raise ValueError(f"Unknown environment: {environment}")
    return LogService(
        selected,
        _provider(selected),
        environment_name=environment,
        file_cache=LogFileCache(_cache_directory()),
    )


def _provider(environment: EnvironmentConfig) -> LocalFileProvider | SshLogProvider:
    if environment.provider == "local":
        return LocalFileProvider(environment.sources)
    if environment.ssh:
        return SshLogProvider(
            environment.ssh.host,
            environment.sources,
            ssh_config=environment.ssh,
        )
    if not environment.ssh_alias:
        raise ValueError("SSH environment must define ssh_alias or ssh")
    return SshLogProvider(environment.ssh_alias, environment.sources)


@mcp.tool()
def list_log_sources(environment: str) -> dict[str, Any]:
    """List approved logical log sources for an environment."""
    return {"sources": [source.to_dict() for source in _service(environment).list_sources()]}


@mcp.tool()
def list_log_files(
    environment: str,
    source: str,
    extract_archives: bool = False,
) -> dict[str, Any]:
    """List and cache all files for a source.

    ZIP files report whether they can be extracted. Only set extract_archives=true after
    the user explicitly confirms that the reported archives should be extracted in place.
    """
    return _service(environment).list_files(
        source,
        extract_archives=extract_archives,
    ).to_dict()


@mcp.tool()
def search_logs(
    environment: str,
    source: str,
    query: str,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Search an approved source; use source/file.log for files under directory sources."""
    matches, truncated = _service(environment).search(
        source,
        query,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
    return {
        "matches": [match.to_dict() for match in matches],
        "truncated": truncated,
    }


@mcp.tool()
def get_log_context(
    environment: str,
    source: str,
    cursor: str,
    before: int = 10,
    after: int = 10,
) -> dict[str, Any]:
    """Read bounded context around a cursor returned by search_logs."""
    lines = _service(environment).context(source, cursor, before=before, after=after)
    return {"lines": [line.to_dict() for line in lines]}


def main() -> None:
    mcp.run(transport="stdio")
