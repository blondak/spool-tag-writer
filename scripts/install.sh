#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON:-python3}"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "Python nebyl nalezen. Nainstaluj Python 3.10+." >&2
    exit 1
  fi
fi

echo "[1/4] Kontrola verze Pythonu..."
"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("Vyžadován Python 3.10+")
print(f"Používám Python {sys.version.split()[0]}")
PY

echo "[2/4] Vytvářím virtualenv: $VENV_DIR"
"$PYTHON_BIN" -m venv "$VENV_DIR"

PIP="$VENV_DIR/bin/pip"
PYTHON_VENV="$VENV_DIR/bin/python"

echo "[3/4] Aktualizuji pip/setuptools/wheel..."
"$PIP" install --upgrade pip setuptools wheel

echo "[4/4] Instaluji Python závislosti..."
"$PIP" install -r requirements.txt

if [[ ! -f "$ROOT_DIR/.env" && -f "$ROOT_DIR/.env.example" ]]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
  echo "Vytvořen .env z .env.example"
fi

cat <<EOF

Instalace dokončena.

Aktivace prostředí:
  source "$VENV_DIR/bin/activate"

Spuštění:
  ./scripts/run.sh web
  ./scripts/run.sh agent
  ./scripts/run.sh both

Poznámka:
  Pokud instalace 'pyscard' selže, doinstaluj systémové PC/SC balíčky
  (např. pcsc-lite + vývojové hlavičky) a spusť install.sh znovu.
EOF
