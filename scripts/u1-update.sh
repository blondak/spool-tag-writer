#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

usage() {
  cat <<'EOF'
Usage:
  u1-update.sh [git-ref]
  u1-update.sh --package-url <url> [--package-header <hdr> ...]
EOF
}

TARGET_REF=""
PACKAGE_URL=""
PACKAGE_HEADERS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --package-url)
      PACKAGE_URL="${2:-}"
      shift 2
      ;;
    --package-header)
      PACKAGE_HEADERS+=("${2:-}")
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      if [[ -n "$TARGET_REF" ]]; then
        echo "Unexpected extra argument: $1" >&2
        usage >&2
        exit 2
      fi
      TARGET_REF="$1"
      shift
      ;;
  esac
done

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

APP_STATE_DIR="${APP_STATE_DIR:-/home/lava/printer_data/system/spool-tag-writer}"

if [[ -n "$PACKAGE_URL" ]]; then
  TMP_DIR="$(mktemp -d)"
  trap 'rm -rf "$TMP_DIR"' EXIT
  PACKAGE_FILE="$TMP_DIR/package.tar.gz"
  CURL_ARGS=(-fsSL)
  for header in "${PACKAGE_HEADERS[@]}"; do
    CURL_ARGS+=(-H "$header")
  done
  curl "${CURL_ARGS[@]}" "$PACKAGE_URL" -o "$PACKAGE_FILE"
  tar -xzf "$PACKAGE_FILE" -C "$TMP_DIR"
  EXTRACTED_DIR="$(find "$TMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  if [[ -z "$EXTRACTED_DIR" ]]; then
    echo "Downloaded package did not contain a top-level directory." >&2
    exit 1
  fi

  find "$ROOT_DIR" -mindepth 1 -maxdepth 1 \
    ! -name '.env' \
    ! -name '.venv' \
    ! -name '.git' \
    ! -name 'node_modules' \
    -exec rm -rf {} +
  cp -a "$EXTRACTED_DIR"/. "$ROOT_DIR"/
else
  git fetch --tags origin

  if [[ -n "$TARGET_REF" ]]; then
    git checkout "$TARGET_REF"
  fi

  git pull --ff-only
fi

"$ROOT_DIR/.venv/bin/pip" install -r "$ROOT_DIR/requirements.txt"

if command -v npm >/dev/null 2>&1; then
  npm ci
  npm run build
elif [[ ! -f "$ROOT_DIR/app/static/dist/index.html" ]]; then
  echo "Frontend build missing and npm is not available." >&2
  echo "Commit prebuilt app/static/dist to the deployed branch, or install npm." >&2
  exit 1
else
  echo "npm not available; using prebuilt app/static/dist from the repository."
fi

python -m compileall app

if [[ -x /etc/init.d/S99spool-tag-writer-web ]]; then
  /etc/init.d/S99spool-tag-writer-web restart
fi

if [[ -x /etc/init.d/S99spool-tag-writer-agent ]]; then
  /etc/init.d/S99spool-tag-writer-agent restart
fi

echo
echo "U1 update finished."
echo "Logs:"
echo "  $APP_STATE_DIR/web.log"
echo "  $APP_STATE_DIR/agent.log"
