#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VERSION="${1:-${PACKAGE_VERSION:-dev}}"
OUT_DIR="${2:-$ROOT_DIR/dist/u1}"
PACKAGE_BASENAME="spool-tag-writer-u1-${VERSION}"
STAGE_DIR="$OUT_DIR/$PACKAGE_BASENAME"

mkdir -p "$OUT_DIR"
rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR"

copy_path() {
  local source="$1"
  if [[ -e "$source" ]]; then
    cp -a "$source" "$STAGE_DIR/"
  fi
}

copy_path app
copy_path frontend
copy_path examples
copy_path scripts
copy_path requirements.txt
copy_path package.json
copy_path package-lock.json
copy_path vite.config.js
copy_path README.md
copy_path LICENSE
copy_path .gitignore

if [[ -f .env.example ]]; then
  cp .env.example "$STAGE_DIR/.env.example"
fi

if [[ ! -f "$STAGE_DIR/app/static/dist/index.html" ]]; then
  echo "Missing built frontend in app/static/dist. Run npm run build first." >&2
  exit 1
fi

printf '%s\n' "$VERSION" >"$STAGE_DIR/VERSION"

(
  cd "$OUT_DIR"
  tar -czf "${PACKAGE_BASENAME}.tar.gz" "$PACKAGE_BASENAME"
  sha256sum "${PACKAGE_BASENAME}.tar.gz" >"${PACKAGE_BASENAME}.tar.gz.sha256"
)

echo "$OUT_DIR/${PACKAGE_BASENAME}.tar.gz"
