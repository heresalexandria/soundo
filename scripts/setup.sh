#!/usr/bin/env bash
set -euo pipefail

SOUNDSLO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOUNDSLO_RUNTIME="$SOUNDSLO_ROOT/.runtime/stable-audio-3"
SOUNDSLO_MLX="$SOUNDSLO_RUNTIME/optimized/mlx"
SOUNDSLO_SA3_REVISION="a0b57f5483c4588f827f3552b7d5c6ca2a9687be"

if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv with the official installer…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "Installing the Soundslo web application…"
cd "$SOUNDSLO_ROOT"
uv sync --dev

if [[ ! -d "$SOUNDSLO_RUNTIME/.git" ]]; then
  echo "Cloning Stability AI's official Stable Audio 3 runtime…"
  mkdir -p "$SOUNDSLO_ROOT/.runtime"
  git clone https://github.com/Stability-AI/stable-audio-3.git "$SOUNDSLO_RUNTIME"
fi

if [[ -n "$(git -C "$SOUNDSLO_RUNTIME" status --porcelain)" ]]; then
  echo "The Stable Audio runtime has local edits; setup will not overwrite them." >&2
  echo "Clean $SOUNDSLO_RUNTIME and run setup again." >&2
  exit 1
fi

echo "Pinning Stable Audio 3 to the tested revision…"
git -C "$SOUNDSLO_RUNTIME" fetch --depth 1 origin "$SOUNDSLO_SA3_REVISION"
git -C "$SOUNDSLO_RUNTIME" checkout --detach "$SOUNDSLO_SA3_REVISION"

echo "Installing the Apple Silicon MLX runtime…"
"$SOUNDSLO_MLX/install.sh" -y

echo "Fetching the text-to-instrumental model files…"
"$SOUNDSLO_MLX/.venv/bin/python" "$SOUNDSLO_ROOT/scripts/prefetch_weights.py" "$SOUNDSLO_MLX"

echo
echo "Soundslo is ready. Start it with:"
echo "  $SOUNDSLO_ROOT/scripts/run.sh"
