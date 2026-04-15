#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  u1-bootstrap.sh (--repo-url <git-url> | --package-url <url>) [options]

Options:
  --repo-url <url>        Git repository URL to clone or update.
  --package-url <url>     Prebuilt U1 package (.tar.gz) URL to download and install.
  --ref <name>            Branch or tag to deploy. Default: main
  --app-dir <path>        Target checkout path.
                          Default: /home/lava/printer_data/apps/spool-tag-writer
  --app-user <user>       Linux user owning the checkout. Default: lava
  --spoolman-url <url>    Value written to SPOOLMAN_URL in .env on first install.
  --app-port <port>       Value written to APP_PORT in .env on first install.
  --package-header <hdr>  Extra HTTP header for package download, may be repeated.
  --force-env-update      Update SPOOLMAN_URL / APP_PORT even when .env already exists.
  --help                  Show this help.
EOF
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

set_env_value() {
  local file="$1"
  local key="$2"
  local value="$3"

  if grep -q "^${key}=" "$file"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$file"
  else
    printf '%s=%s\n' "$key" "$value" >>"$file"
  fi
}

REPO_URL=""
PACKAGE_URL=""
REPO_REF="main"
APP_DIR="/home/lava/printer_data/apps/spool-tag-writer"
APP_USER="lava"
SPOOLMAN_URL=""
APP_PORT=""
FORCE_ENV_UPDATE=0
PACKAGE_HEADERS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-url)
      REPO_URL="${2:-}"
      shift 2
      ;;
    --package-url)
      PACKAGE_URL="${2:-}"
      shift 2
      ;;
    --ref)
      REPO_REF="${2:-}"
      shift 2
      ;;
    --app-dir)
      APP_DIR="${2:-}"
      shift 2
      ;;
    --app-user)
      APP_USER="${2:-}"
      shift 2
      ;;
    --spoolman-url)
      SPOOLMAN_URL="${2:-}"
      shift 2
      ;;
    --app-port)
      APP_PORT="${2:-}"
      shift 2
      ;;
    --package-header)
      PACKAGE_HEADERS+=("${2:-}")
      shift 2
      ;;
    --force-env-update)
      FORCE_ENV_UPDATE=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$REPO_URL" && -z "$PACKAGE_URL" ]]; then
  echo "Either --repo-url or --package-url is required." >&2
  usage >&2
  exit 2
fi

if [[ -n "$REPO_URL" && -n "$PACKAGE_URL" ]]; then
  echo "Use either --repo-url or --package-url, not both." >&2
  usage >&2
  exit 2
fi

require_command python3
if [[ -n "$REPO_URL" ]]; then
  require_command git
fi
if [[ -n "$PACKAGE_URL" ]]; then
  require_command curl
  require_command tar
fi

APP_PARENT_DIR="$(dirname "$APP_DIR")"
mkdir -p "$APP_PARENT_DIR"

if [[ -n "$REPO_URL" ]]; then
  if [[ -d "$APP_DIR/.git" ]]; then
    git -C "$APP_DIR" diff --quiet || {
      echo "Existing checkout in $APP_DIR has local changes; aborting." >&2
      exit 1
    }
    git -C "$APP_DIR" fetch --tags origin
    git -C "$APP_DIR" checkout "$REPO_REF"
    git -C "$APP_DIR" pull --ff-only origin "$REPO_REF"
  else
    rm -rf "$APP_DIR"
    git clone --branch "$REPO_REF" --single-branch "$REPO_URL" "$APP_DIR"
  fi
else
  TMP_DIR="$(mktemp -d)"
  PACKAGE_FILE="$TMP_DIR/package.tar.gz"
  CURL_ARGS=(-fsSL)
  for header in "${PACKAGE_HEADERS[@]}"; do
    CURL_ARGS+=(-H "$header")
  done
  curl "${CURL_ARGS[@]}" "$PACKAGE_URL" -o "$PACKAGE_FILE"

  rm -rf "$APP_DIR"
  mkdir -p "$APP_DIR"
  tar -xzf "$PACKAGE_FILE" -C "$TMP_DIR"

  EXTRACTED_DIR="$(find "$TMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  if [[ -z "$EXTRACTED_DIR" ]]; then
    echo "Downloaded package did not contain a top-level directory." >&2
    exit 1
  fi
  cp -a "$EXTRACTED_DIR"/. "$APP_DIR"/
fi

cd "$APP_DIR"

ENV_FILE="$APP_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  cp "$APP_DIR/examples/u1/.env.u1.example" "$ENV_FILE"
  CREATED_ENV=1
else
  CREATED_ENV=0
fi

if [[ -n "$SPOOLMAN_URL" && ( $CREATED_ENV -eq 1 || $FORCE_ENV_UPDATE -eq 1 ) ]]; then
  set_env_value "$ENV_FILE" "SPOOLMAN_URL" "$SPOOLMAN_URL"
fi

if [[ -n "$APP_PORT" && ( $CREATED_ENV -eq 1 || $FORCE_ENV_UPDATE -eq 1 ) ]]; then
  set_env_value "$ENV_FILE" "APP_PORT" "$APP_PORT"
  set_env_value "$ENV_FILE" "MOONRAKER_CLIENT_URL" "http://127.0.0.1:${APP_PORT}"
fi

set_env_value "$ENV_FILE" "APP_DIR" "$APP_DIR"
set_env_value "$ENV_FILE" "APP_USER" "$APP_USER"

chmod +x "$APP_DIR/scripts/u1-install.sh" "$APP_DIR/scripts/u1-update.sh"
"$APP_DIR/scripts/u1-install.sh" --install-services

chown -R "$APP_USER":"$APP_USER" "$APP_DIR" 2>/dev/null || true

echo
echo "Bootstrap finished."
echo "Checkout: $APP_DIR"
if [[ -n "$REPO_URL" ]]; then
  echo "Ref:      $REPO_REF"
else
  echo "Package:  $PACKAGE_URL"
fi
echo "Open UI:  http://$(hostname -I 2>/dev/null | awk '{print $1}'):${APP_PORT:-18080}/"
