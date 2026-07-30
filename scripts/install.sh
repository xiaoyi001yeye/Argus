#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="${ARGUS_INSTALL_DIR:-"$HOME/.local/share/argus"}"
CONFIG_PATH="${ARGUS_CONFIG:-"$HOME/.config/argus/environments.yaml"}"
PYTHON_BIN="${PYTHON:-python3}"
PACKAGE_SPEC="$PROJECT_ROOT"

if [[ "${ARGUS_WITH_DEV:-0}" == "1" ]]; then
  PACKAGE_SPEC="$PROJECT_ROOT[dev]"
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python executable not found: $PYTHON_BIN" >&2
  exit 1
fi

mkdir -p "$INSTALL_DIR" "$(dirname "$CONFIG_PATH")"
"$PYTHON_BIN" -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/python" -m pip install --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install "$PACKAGE_SPEC"

if [[ ! -f "$CONFIG_PATH" ]]; then
  cp "$PROJECT_ROOT/config/environments.example.yaml" "$CONFIG_PATH"
  chmod 600 "$CONFIG_PATH"
  CONFIG_CREATED=1
else
  CONFIG_CREATED=0
fi

cat <<EOF
Argus installed successfully.

Command:
  $INSTALL_DIR/.venv/bin/argus

Config:
  $CONFIG_PATH
EOF

if [[ "$CONFIG_CREATED" == "1" ]]; then
  cat <<EOF

A starter config was created. Edit it before using production logs.
EOF
fi

cat <<EOF

Codex MCP registration:
  codex mcp add argus \\
    --env ARGUS_CONFIG=$CONFIG_PATH \\
    -- $INSTALL_DIR/.venv/bin/argus

Manual MCP command:
  command = "$INSTALL_DIR/.venv/bin/argus"
  env ARGUS_CONFIG = "$CONFIG_PATH"
EOF
