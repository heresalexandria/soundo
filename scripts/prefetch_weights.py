#!/usr/bin/env python3
"""Download only the weights required for Medium text-to-audio."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TEXT_TO_AUDIO_WEIGHTS = (
    "models/mlx/t5gemma_f16.npz",
    "models/mlx/dit_medium_f16.npz",
    "models/mlx/same_l_decoder_f32.npz",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mlx_root", type=Path)
    args = parser.parse_args()
    scripts_dir = args.mlx_root.resolve() / "scripts"
    if not (scripts_dir / "weights.py").is_file():
        raise SystemExit(f"Stable Audio MLX scripts not found at {scripts_dir}")
    sys.path.insert(0, str(scripts_dir))

    from weights import ensure_local  # noqa: PLC0415

    print("Downloading the Medium text-to-audio weights (the encoder is intentionally skipped).")
    for relative_path in TEXT_TO_AUDIO_WEIGHTS:
        path = ensure_local(relative_path)
        print(f"  ready: {path.name}")


if __name__ == "__main__":
    main()
