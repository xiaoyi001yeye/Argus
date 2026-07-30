#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$("$PROJECT_ROOT/.venv/bin/python" -c "import tomllib; print(tomllib.load(open('$PROJECT_ROOT/pyproject.toml', 'rb'))['project']['version'])" 2>/dev/null || true)"

if [[ -z "$VERSION" ]]; then
  VERSION="$(python3 -c "import tomllib; print(tomllib.load(open('$PROJECT_ROOT/pyproject.toml', 'rb'))['project']['version'])")"
fi

PACKAGE_NAME="argus-installer-$VERSION"
BUILD_DIR="$PROJECT_ROOT/build/$PACKAGE_NAME"
ARCHIVE_PATH="$PROJECT_ROOT/dist/$PACKAGE_NAME.tar.gz"

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR" "$PROJECT_ROOT/dist"

rsync -a \
  --exclude ".git" \
  --exclude ".idea" \
  --exclude ".pytest_cache" \
  --exclude ".ruff_cache" \
  --exclude ".serena" \
  --exclude ".venv" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  --exclude "build" \
  --exclude "dist" \
  --exclude "config/environments.yaml" \
  "$PROJECT_ROOT/" "$BUILD_DIR/"

chmod +x "$BUILD_DIR/scripts/install.sh"
tar -C "$PROJECT_ROOT/build" -czf "$ARCHIVE_PATH" "$PACKAGE_NAME"

cat <<EOF
Created installer package:
  $ARCHIVE_PATH

Install on a target machine:
  tar -xzf $PACKAGE_NAME.tar.gz
  cd $PACKAGE_NAME
  ./scripts/install.sh
EOF
