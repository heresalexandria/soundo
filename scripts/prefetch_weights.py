#!/usr/bin/env python3
"""Download only the weights required for Medium text-to-audio."""

from __future__ import annotations

import argparse
from pathlib import Path

REPO_ID = "stabilityai/stable-audio-3-optimized"
TEXT_TO_AUDIO_WEIGHTS = (
    ("models/mlx/t5gemma_f16.npz", "MLX/t5gemma_f16.npz"),
    ("models/mlx/dit_medium_f16.npz", "MLX/dit_medium_f16.npz"),
    ("models/mlx/same_l_decoder_f32.npz", "MLX/same_l_decoder_f32.npz"),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mlx_root", type=Path)
    parser.add_argument("--revision", required=True, help="Pinned Hugging Face commit")
    args = parser.parse_args()
    mlx_root = args.mlx_root.resolve()
    if not (mlx_root / "scripts" / "weights.py").is_file():
        raise SystemExit(f"Stable Audio MLX scripts not found at {mlx_root / 'scripts'}")

    from huggingface_hub import hf_hub_download  # noqa: PLC0415

    print(f"Downloading pinned Medium text-to-audio weights ({args.revision[:12]}).")
    for relative_path, remote_path in TEXT_TO_AUDIO_WEIGHTS:
        cached = Path(
            hf_hub_download(repo_id=REPO_ID, filename=remote_path, revision=args.revision)
        )
        target = mlx_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink() or target.exists():
            target.unlink()
        target.symlink_to(cached)
        print(f"  ready: {target.name}")


if __name__ == "__main__":
    main()
