#!/usr/bin/env bash
set -euo pipefail

SOUNDSLO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOUNDSLO_MLX="$SOUNDSLO_ROOT/.runtime/stable-audio-3/optimized/mlx"
SOUNDSLO_PYTHON="$SOUNDSLO_MLX/.venv/bin/python"
SOUNDSLO_WEIGHTS_REVISION="6736003cb57d06b7b1fdc36fad31b2a3709e4774"
SOUNDSLO_MODEL="${1:-}"

case "$SOUNDSLO_MODEL" in
  small-music|sm-music)
    SOUNDSLO_MODEL="sm-music"
    ;;
  medium)
    ;;
  large|large-api)
    echo "Stable Audio 3 Large has no public local or Hugging Face weights." >&2
    echo "Stability AI provides it only through its hosted API or an enterprise agreement." >&2
    echo "To use the hosted model, set STABILITY_API_KEY before starting Soundslo." >&2
    exit 2
    ;;
  *)
    echo "Usage: $0 {small-music|medium|large}" >&2
    exit 2
    ;;
esac

if [[ ! -x "$SOUNDSLO_PYTHON" ]]; then
  echo "The Stable Audio MLX runtime is missing. Run ./scripts/setup.sh first." >&2
  exit 1
fi

exec "$SOUNDSLO_PYTHON" "$SOUNDSLO_ROOT/scripts/prefetch_weights.py" \
  "$SOUNDSLO_MLX" \
  --revision "$SOUNDSLO_WEIGHTS_REVISION" \
  --model "$SOUNDSLO_MODEL"
