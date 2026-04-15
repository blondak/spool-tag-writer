#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "u1-recover.sh must be run as root." >&2
  exit 1
fi

touch /oem/.debug

cd "$ROOT_DIR"
"$ROOT_DIR/scripts/u1-install.sh" --install-services

echo
echo "U1 recovery finished."
echo "Re-enabled: /oem/.debug"
echo "Reinstalled services from: $ROOT_DIR"
