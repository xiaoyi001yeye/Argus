# Argus

Argus is a safety-first MCP server for retrieving logs from approved sources and
giving an AI client enough evidence to diagnose incidents.

The first milestone deliberately uses local files. The SSH boundary is already
defined, but arbitrary hosts, paths, and shell commands are not exposed to the
AI client.

## MCP tools

- `list_log_sources(environment)` lists configured, allowed sources.
- `search_logs(source, start_time, end_time, query, limit)` finds relevant lines.
- `get_log_context(source, cursor, before, after)` reads surrounding evidence.

## Quick start

Requires Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp config/environments.example.yaml config/environments.yaml
argus
```

For a quick local check:

```bash
pytest
```

Point an MCP client at the `argus` command. Set `ARGUS_CONFIG` if the
configuration is not at `config/environments.yaml`.

## Documentation

- [在 Codex 中使用 Argus](docs/CODEX_USAGE_ZH.md): installation, MCP configuration,
  verification, and an end-to-end diagnostic example.
- [环境管理说明](docs/ENVIRONMENT_MANAGEMENT_ZH.md): local and SSH environment
  configuration, credential storage, log-source allow lists, validation, and
  operational security.

## Project layout

```text
src/argus/
├── server.py       # MCP boundary
├── service.py      # safe log operations
├── config.py       # allow-list configuration
├── models.py       # tool input/output models
├── redaction.py    # basic secret masking
└── providers/
    ├── base.py     # backend contract
    ├── local.py    # MVP local-file backend
    └── ssh.py      # next milestone boundary
```

See [MVP_SPEC.md](MVP_SPEC.md) for scope, security rules, and acceptance
criteria.
