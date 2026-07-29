from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from argus.config import EnvironmentConfig, load_config
from argus.providers.local import LocalFileProvider
from argus.providers.ssh import SshLogProvider
from argus.service import LogService

mcp = FastMCP("Argus")


def _config_path() -> Path:
    return Path(os.environ.get("ARGUS_CONFIG", "config/environments.yaml")).resolve()


def _service(environment: str) -> LogService:
    config = load_config(_config_path())
    selected = config.environments.get(environment)
    if selected is None:
        raise ValueError(f"Unknown environment: {environment}")
    return LogService(selected, _provider(selected))


def _provider(environment: EnvironmentConfig) -> LocalFileProvider | SshLogProvider:
    if environment.provider == "local":
        return LocalFileProvider(environment.sources)
    if not environment.ssh_alias:
        raise ValueError("SSH environment must define ssh_alias")
    return SshLogProvider(environment.ssh_alias, environment.sources)


@mcp.tool()
def list_log_sources(environment: str) -> dict[str, Any]:
    """List approved logical log sources for an environment."""
    return {"sources": [source.to_dict() for source in _service(environment).list_sources()]}


@mcp.tool()
def search_logs(
    environment: str,
    source: str,
    query: str,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Search an approved source; query accepts plain terms separated by OR."""
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
