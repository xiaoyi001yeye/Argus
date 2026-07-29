from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when Argus configuration is invalid."""


@dataclass(frozen=True, slots=True)
class SourceConfig:
    path: Path
    description: str = ""


@dataclass(frozen=True, slots=True)
class EnvironmentConfig:
    provider: str
    sources: dict[str, SourceConfig]
    ssh_alias: str | None = None


@dataclass(frozen=True, slots=True)
class ArgusConfig:
    environments: dict[str, EnvironmentConfig]


def load_config(path: Path) -> ArgusConfig:
    if not path.is_file():
        raise ConfigError(f"Configuration file not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    environments_raw = raw.get("environments")
    if not isinstance(environments_raw, dict) or not environments_raw:
        raise ConfigError("'environments' must be a non-empty mapping")

    environments: dict[str, EnvironmentConfig] = {}
    for env_name, env_raw in environments_raw.items():
        environments[env_name] = _parse_environment(env_name, env_raw, path.parent.parent)
    return ArgusConfig(environments=environments)


def _parse_environment(name: str, raw: Any, project_root: Path) -> EnvironmentConfig:
    if not isinstance(raw, dict):
        raise ConfigError(f"Environment '{name}' must be a mapping")
    provider = raw.get("provider", "local")
    if provider not in {"local", "ssh"}:
        raise ConfigError(f"Environment '{name}' has unsupported provider '{provider}'")

    sources_raw = raw.get("log_sources")
    if not isinstance(sources_raw, dict) or not sources_raw:
        raise ConfigError(f"Environment '{name}' must define log_sources")

    sources: dict[str, SourceConfig] = {}
    for source_id, source_raw in sources_raw.items():
        if not isinstance(source_raw, dict) or not isinstance(source_raw.get("path"), str):
            raise ConfigError(f"Source '{source_id}' must define a string path")
        source_path = Path(source_raw["path"])
        if provider == "local" and not source_path.is_absolute():
            source_path = (project_root / source_path).resolve()
        sources[source_id] = SourceConfig(
            path=source_path,
            description=str(source_raw.get("description", "")),
        )

    return EnvironmentConfig(
        provider=provider,
        sources=sources,
        ssh_alias=raw.get("ssh_alias"),
    )
