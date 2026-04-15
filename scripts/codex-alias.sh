#!/usr/bin/env bash
# Source this file in your shell to run project wrapper as plain `codex`.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
alias codex="$ROOT_DIR/scripts/codex"
