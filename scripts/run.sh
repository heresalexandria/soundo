#!/usr/bin/env bash
set -euo pipefail

SOUNDSLO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOUNDSLO_PORT="${SOUNDSLO_PORT:-8733}"
SOUNDSLO_URL="http://127.0.0.1:$SOUNDSLO_PORT"

cd "$SOUNDSLO_ROOT"
if ! command -v uv >/dev/null 2>&1; then
  export PATH="$HOME/.local/bin:$PATH"
fi

if [[ ! -x "$SOUNDSLO_ROOT/.venv/bin/python" ]]; then
  echo "Soundslo has not been installed. Run ./scripts/setup.sh first." >&2
  exit 1
fi

echo "Opening Soundslo at $SOUNDSLO_URL"
(sleep 1 && open "$SOUNDSLO_URL") &
exec uv run uvicorn soundslo.app:app --host 127.0.0.1 --port "$SOUNDSLO_PORT"
