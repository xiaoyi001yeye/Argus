#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-"$PROJECT_ROOT/.venv/bin/python"}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="${PYTHON:-python3}"
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python executable not found: $PYTHON_BIN" >&2
  exit 1
fi

"$PYTHON_BIN" -m pip install --upgrade build
"$PYTHON_BIN" -m build "$PROJECT_ROOT"

cat <<EOF
Python package artifacts created in:
  $PROJECT_ROOT/dist

Install with pip:
  python3 -m pip install $PROJECT_ROOT/dist/argus_log_diagnostics-*.whl

Install as an isolated CLI with pipx:
  pipx install $PROJECT_ROOT/dist/argus_log_diagnostics-*.whl
EOF
