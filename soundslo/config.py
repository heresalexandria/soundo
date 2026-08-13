from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SA3_REVISION = "a0b57f5483c4588f827f3552b7d5c6ca2a9687be"
SA3_WEIGHTS_REVISION = "6736003cb57d06b7b1fdc36fad31b2a3709e4774"


@dataclass(frozen=True)
class Settings:
    root: Path
    data_dir: Path
    database_path: Path
    generations_dir: Path
    sa3_root: Path
    static_dir: Path
    stability_api_key: str | None = None
    stability_api_base_url: str = "https://api.stability.ai"

    @classmethod
    def from_env(cls) -> Settings:
        root = Path(os.environ.get("SOUNDSLO_ROOT", ROOT)).expanduser().resolve()
        data_dir = Path(os.environ.get("SOUNDSLO_DATA_DIR", root / "data")).expanduser().resolve()
        sa3_root = (
            Path(os.environ.get("SOUNDSLO_SA3_ROOT", root / ".runtime" / "stable-audio-3"))
            .expanduser()
            .resolve()
        )
        return cls(
            root=root,
            data_dir=data_dir,
            database_path=data_dir / "soundslo.sqlite3",
            generations_dir=data_dir / "generations",
            sa3_root=sa3_root,
            static_dir=root / "soundslo" / "static",
            stability_api_key=os.environ.get("STABILITY_API_KEY") or None,
            stability_api_base_url=os.environ.get(
                "STABILITY_API_BASE_URL", "https://api.stability.ai"
            ).rstrip("/"),
        )

    @property
    def mlx_root(self) -> Path:
        return self.sa3_root / "optimized" / "mlx"

    @property
    def sa3_executable(self) -> Path:
        return self.mlx_root / "sa3"

    @property
    def runtime_python(self) -> Path:
        return self.mlx_root / ".venv" / "bin" / "python"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.generations_dir.mkdir(parents=True, exist_ok=True)
