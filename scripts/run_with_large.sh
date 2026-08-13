#!/usr/bin/env bash
set -euo pipefail

SOUNDSLO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -z "${STABILITY_API_KEY:-}" ]]; then
  printf "Stability API key (input hidden): " >&2
  read -rs STABILITY_API_KEY
  printf "\n" >&2
  if [[ -z "$STABILITY_API_KEY" ]]; then
    echo "No key entered. Nothing was stored." >&2
    exit 1
  fi
  export STABILITY_API_KEY
fi

exec "$SOUNDSLO_ROOT/scripts/run.sh"
