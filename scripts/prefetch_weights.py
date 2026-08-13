#!/usr/bin/env python3
"""Download a pinned Stable Audio 3 MLX text-to-music bundle."""

from __future__ import annotations

import argparse
from pathlib import Path

REPO_ID = "stabilityai/stable-audio-3-optimized"
SHARED_TEXT_ENCODER = ("models/mlx/t5gemma_f16.npz", "MLX/t5gemma_f16.npz")
MODEL_WEIGHTS = {
    "sm-music": (
        SHARED_TEXT_ENCODER,
        ("models/mlx/dit_sm-music_f16.npz", "MLX/dit_sm-music_f16.npz"),
        ("models/mlx/same_s_decoder_f32.npz", "MLX/same_s_decoder_f32.npz"),
    ),
    "medium": (
        SHARED_TEXT_ENCODER,
        ("models/mlx/dit_medium_f16.npz", "MLX/dit_medium_f16.npz"),
        ("models/mlx/same_l_decoder_f32.npz", "MLX/same_l_decoder_f32.npz"),
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mlx_root", type=Path)
    parser.add_argument("--revision", required=True, help="Pinned Hugging Face commit")
    parser.add_argument("--model", choices=MODEL_WEIGHTS, default="medium")
    args = parser.parse_args()
    mlx_root = args.mlx_root.resolve()
    if not (mlx_root / "scripts" / "weights.py").is_file():
        raise SystemExit(f"Stable Audio MLX scripts not found at {mlx_root / 'scripts'}")

    from huggingface_hub import hf_hub_download  # noqa: PLC0415

    print(
        f"Downloading pinned Stable Audio 3 {args.model} text-to-music weights "
        f"({args.revision[:12]}).",
        flush=True,
    )
    for relative_path, remote_path in MODEL_WEIGHTS[args.model]:
        print(f"fetching: {Path(remote_path).name}", flush=True)
        cached = Path(
            hf_hub_download(repo_id=REPO_ID, filename=remote_path, revision=args.revision)
        )
        target = mlx_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink() or target.exists():
            target.unlink()
        target.symlink_to(cached)
        print(f"ready: {target.name}", flush=True)


if __name__ == "__main__":
    main()
