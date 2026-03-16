#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${1:-web}"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

VENV_BIN_DEFAULT="$ROOT_DIR/.venv/bin"
PYTHON="${PYTHON:-$VENV_BIN_DEFAULT/python}"
UVICORN="${UVICORN:-$VENV_BIN_DEFAULT/uvicorn}"
HOST="${HOST:-${APP_HOST:-0.0.0.0}}"
PORT="${PORT:-${APP_PORT:-8080}}"
RELOAD="${RELOAD:-0}"

if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3 || true)"
fi
if [[ -z "${PYTHON:-}" ]]; then
  echo "Python nebyl nalezen. Vytvor .venv nebo nastav PYTHON." >&2
  exit 1
fi

if [[ ! -x "$UVICORN" ]]; then
  UVICORN=""
fi

run_web() {
  local reload_flag=()
  if [[ "$RELOAD" == "1" ]]; then
    reload_flag=(--reload)
  fi
  if [[ -n "$UVICORN" ]]; then
    exec "$UVICORN" app.main:app --host "$HOST" --port "$PORT" "${reload_flag[@]}"
  fi
  exec "$PYTHON" -m uvicorn app.main:app --host "$HOST" --port "$PORT" "${reload_flag[@]}"
}

run_agent() {
  exec "$PYTHON" -m app.moonraker_agent
}

run_both() {
  local reload_flag=()
  if [[ "$RELOAD" == "1" ]]; then
    reload_flag=(--reload)
  fi

  if [[ -n "$UVICORN" ]]; then
    "$UVICORN" app.main:app --host "$HOST" --port "$PORT" "${reload_flag[@]}" &
  else
    "$PYTHON" -m uvicorn app.main:app --host "$HOST" --port "$PORT" "${reload_flag[@]}" &
  fi
  local web_pid=$!

  "$PYTHON" -m app.moonraker_agent &
  local agent_pid=$!

  cleanup() {
    kill "$web_pid" "$agent_pid" 2>/dev/null || true
  }
  trap cleanup INT TERM EXIT

  wait -n "$web_pid" "$agent_pid"
}

case "$MODE" in
  web)
    run_web
    ;;
  agent)
    run_agent
    ;;
  both)
    run_both
    ;;
  *)
    echo "Pouziti: $0 [web|agent|both]" >&2
    exit 2
    ;;
esac
