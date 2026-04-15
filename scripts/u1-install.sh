#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

INSTALL_SERVICES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-services)
      INSTALL_SERVICES=1
      shift
      ;;
    *)
      echo "Usage: $0 [--install-services]" >&2
      exit 2
      ;;
  esac
done

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

APP_DIR="${APP_DIR:-$ROOT_DIR}"
APP_USER="${APP_USER:-lava}"
APP_STATE_DIR="${APP_STATE_DIR:-/home/lava/printer_data/system/spool-tag-writer}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ ! -f "$ROOT_DIR/.env" && -f "$ROOT_DIR/examples/u1/.env.u1.example" ]]; then
  cp "$ROOT_DIR/examples/u1/.env.u1.example" "$ROOT_DIR/.env"
  echo "Created .env from examples/u1/.env.u1.example"
fi

mkdir -p "$APP_STATE_DIR"

if [[ ! -d "$ROOT_DIR/.venv" ]]; then
  "$PYTHON_BIN" -m venv "$ROOT_DIR/.venv"
fi

"$ROOT_DIR/.venv/bin/pip" install --upgrade pip
"$ROOT_DIR/.venv/bin/pip" install -r "$ROOT_DIR/requirements.txt"

if command -v npm >/dev/null 2>&1; then
  npm ci
  npm run build
elif [[ ! -f "$ROOT_DIR/app/static/dist/index.html" ]]; then
  echo "Frontend build missing and npm is not available." >&2
  echo "Commit prebuilt app/static/dist to the branch used on the printer, or install npm." >&2
  exit 1
else
  echo "npm not available; using prebuilt app/static/dist from the repository."
fi

if [[ $INSTALL_SERVICES -eq 1 ]]; then
  install -m 0755 "$ROOT_DIR/examples/u1/init.d/spool-tag-writer-web" /etc/init.d/S99spool-tag-writer-web
  install -m 0755 "$ROOT_DIR/examples/u1/init.d/spool-tag-writer-agent" /etc/init.d/S99spool-tag-writer-agent
  /etc/init.d/S99spool-tag-writer-web restart
  /etc/init.d/S99spool-tag-writer-agent restart
fi

chown -R "$APP_USER":"$APP_USER" "$ROOT_DIR/.venv" "$APP_STATE_DIR" 2>/dev/null || true

echo
echo "U1 install finished."
echo "App dir: $APP_DIR"
echo "State dir: $APP_STATE_DIR"
if [[ $INSTALL_SERVICES -eq 1 ]]; then
  echo "Services installed:"
  echo "  /etc/init.d/S99spool-tag-writer-web"
  echo "  /etc/init.d/S99spool-tag-writer-agent"
fi
