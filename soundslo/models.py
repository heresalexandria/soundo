from __future__ import annotations

import subprocess
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Literal

from soundslo.config import SA3_WEIGHTS_REVISION, Settings

SMALL_MUSIC_ID = "stable-audio-3-small-music"
MEDIUM_ID = "stable-audio-3-medium"
LARGE_API_ID = "stable-audio-3-large-api"


@dataclass(frozen=True)
class ModelSpec:
    id: str
    name: str
    short_name: str
    deployment: Literal["local", "cloud"]
    description: str
    tradeoff: str
    parameter_label: str
    max_duration_seconds: int
    min_duration_seconds: int
    default_steps: int
    max_steps: int
    supports_negative_prompt: bool
    weight_files: tuple[str, ...] = ()
    download_bytes: int | None = None
    dit: str | None = None
    decoder: str | None = None
    api_model: str | None = None
    credits_per_generation: int | None = None
    official_url: str = "https://github.com/Stability-AI/stable-audio-3"

    @property
    def revision(self) -> str:
        return SA3_WEIGHTS_REVISION if self.deployment == "local" else "api-managed"


MODEL_SPECS = {
    SMALL_MUSIC_ID: ModelSpec(
        id=SMALL_MUSIC_ID,
        name="Stable Audio 3 Small Music",
        short_name="Small Music",
        deployment="local",
        description="Fast, lightweight music generation for lower-memory Apple Silicon Macs.",
        tradeoff=(
            "Uses much less disk and memory than Medium, but tops out at two minutes "
            "and has lower musical coherence."
        ),
        parameter_label="433M",
        max_duration_seconds=120,
        min_duration_seconds=1,
        default_steps=8,
        max_steps=32,
        supports_negative_prompt=True,
        weight_files=(
            "models/mlx/t5gemma_f16.npz",
            "models/mlx/dit_sm-music_f16.npz",
            "models/mlx/same_s_decoder_f32.npz",
        ),
        download_bytes=1_704_727_702,
        dit="sm-music",
        decoder="same-s",
        official_url="https://huggingface.co/stabilityai/stable-audio-3-small",
    ),
    MEDIUM_ID: ModelSpec(
        id=MEDIUM_ID,
        name="Stable Audio 3 Medium",
        short_name="Medium",
        deployment="local",
        description=(
            "The highest-quality Stable Audio 3 model with publicly downloadable local weights."
        ),
        tradeoff=(
            "Better structure, melodic coherence, and phrasing than Small, with a larger "
            "memory and storage footprint."
        ),
        parameter_label="1.4B",
        max_duration_seconds=380,
        min_duration_seconds=1,
        default_steps=8,
        max_steps=32,
        supports_negative_prompt=True,
        weight_files=(
            "models/mlx/t5gemma_f16.npz",
            "models/mlx/dit_medium_f16.npz",
            "models/mlx/same_l_decoder_f32.npz",
        ),
        download_bytes=5_179_055_990,
        dit="medium",
        decoder="same-l",
        official_url="https://huggingface.co/stabilityai/stable-audio-3-medium",
    ),
    LARGE_API_ID: ModelSpec(
        id=LARGE_API_ID,
        name="Stable Audio 3 Large",
        short_name="Large API",
        deployment="cloud",
        description=(
            "Stability AI's highest-musicality Stable Audio 3 model, available through "
            "its hosted API."
        ),
        tradeoff=(
            "No public local weights: prompts leave this Mac, internet and an API key are "
            "required, and each successful generation costs credits."
        ),
        parameter_label="2.7B",
        max_duration_seconds=380,
        min_duration_seconds=1,
        default_steps=8,
        max_steps=8,
        supports_negative_prompt=False,
        api_model="stable-audio-3",
        credits_per_generation=26,
        official_url="https://platform.stability.ai/docs/api-reference#tag/Stable-Audio-3.0",
    ),
}


def get_model(model_id: str) -> ModelSpec:
    try:
        return MODEL_SPECS[model_id]
    except KeyError as error:
        raise ValueError(f"Unknown model: {model_id}") from error


def model_is_installed(settings: Settings, spec: ModelSpec) -> bool:
    return bool(spec.weight_files) and all(
        (settings.mlx_root / relative_path).is_file() for relative_path in spec.weight_files
    )


def model_is_ready(settings: Settings, spec: ModelSpec) -> bool:
    if spec.deployment == "cloud":
        return bool(settings.stability_api_key)
    return (
        settings.sa3_executable.is_file()
        and settings.runtime_python.is_file()
        and model_is_installed(settings, spec)
    )


def model_catalog(settings: Settings) -> list[dict]:
    runtime_installed = settings.sa3_executable.is_file() and settings.runtime_python.is_file()
    catalog: list[dict] = []
    for spec in MODEL_SPECS.values():
        installed = model_is_installed(settings, spec) if spec.deployment == "local" else False
        details = asdict(spec)
        details.update(
            {
                "installed": installed,
                "installed_bytes": _installed_bytes(settings, spec),
                "ready": model_is_ready(settings, spec),
                "runtime_installed": runtime_installed,
                "installable": spec.deployment == "local",
                "configured": (
                    installed if spec.deployment == "local" else bool(settings.stability_api_key)
                ),
                "revision": spec.revision,
                "install_command": (
                    f"bash scripts/install_model.sh {spec.dit}"
                    if spec.deployment == "local"
                    else None
                ),
                "credential_note": (
                    "Hugging Face may require a free account, license acceptance, and "
                    "hf auth login."
                    if spec.deployment == "local"
                    else (
                        "Set STABILITY_API_KEY before starting Soundslo. The key is never "
                        "returned to the browser."
                    )
                ),
            }
        )
        catalog.append(details)
    return catalog


def _installed_bytes(settings: Settings, spec: ModelSpec) -> int:
    total = 0
    for relative_path in spec.weight_files:
        path = settings.mlx_root / relative_path
        try:
            total += path.stat().st_size
        except OSError:
            continue
    return total


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class ModelInstaller:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._lock = threading.Lock()
        self._statuses: dict[str, dict] = {}

    def status(self, model_id: str) -> dict:
        with self._lock:
            status = self._statuses.get(model_id)
            if status:
                return dict(status)
        spec = get_model(model_id)
        if model_is_ready(self.settings, spec):
            return self._status(model_id, "complete", 100, "Ready")
        return self._status(model_id, "idle", 0, "Not installed")

    def start(self, model_id: str) -> dict:
        spec = get_model(model_id)
        if spec.deployment != "local":
            raise ValueError(
                "Stable Audio 3 Large is API-only and has no public Hugging Face weights "
                "to install."
            )
        if not self.settings.runtime_python.is_file():
            raise RuntimeError("The MLX runtime is missing. Run ./scripts/setup.sh first.")
        with self._lock:
            current = self._statuses.get(model_id)
            if current and current["state"] == "installing":
                return dict(current)
            if model_is_installed(self.settings, spec):
                current = self._status(model_id, "complete", 100, "Ready")
                self._statuses[model_id] = current
                return dict(current)
            status = self._status(model_id, "installing", 2, "Preparing download")
            status["started_at"] = _utc_now()
            self._statuses[model_id] = status
        thread = threading.Thread(
            target=self._install,
            args=(spec,),
            name=f"soundslo-install-{spec.dit}",
            daemon=True,
        )
        thread.start()
        return dict(status)

    def _install(self, spec: ModelSpec) -> None:
        command = [
            str(self.settings.runtime_python),
            str(self.settings.root / "scripts" / "prefetch_weights.py"),
            str(self.settings.mlx_root),
            "--revision",
            SA3_WEIGHTS_REVISION,
            "--model",
            str(spec.dit),
        ]
        output: list[str] = []
        try:
            process = subprocess.Popen(
                command,
                cwd=self.settings.root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert process.stdout is not None
            ready_count = 0
            total = max(len(spec.weight_files), 1)
            for line in process.stdout:
                clean = line.strip()
                if not clean:
                    continue
                output.append(clean)
                if clean.startswith("fetching:"):
                    self._update(
                        spec.id,
                        progress=8 + (ready_count / total) * 82,
                        stage=f"Downloading {clean.removeprefix('fetching:').strip()}",
                    )
                elif clean.startswith("ready:"):
                    ready_count += 1
                    self._update(
                        spec.id,
                        progress=8 + (ready_count / total) * 88,
                        stage=f"Installed {ready_count} of {total} files",
                    )
            return_code = process.wait()
            if return_code != 0:
                raise RuntimeError(
                    output[-1] if output else f"Installer exited with {return_code}."
                )
            if not model_is_installed(self.settings, spec):
                raise RuntimeError(
                    "Download finished but one or more model files are still missing."
                )
            self._update(
                spec.id,
                state="complete",
                progress=100,
                stage="Ready",
                error=None,
                finished_at=_utc_now(),
            )
        except Exception as error:
            self._update(
                spec.id,
                state="failed",
                stage="Installation failed",
                error=str(error),
                finished_at=_utc_now(),
            )

    def _update(self, model_id: str, **values: object) -> None:
        with self._lock:
            self._statuses[model_id].update(values)

    @staticmethod
    def _status(model_id: str, state: str, progress: float, stage: str) -> dict:
        return {
            "model": model_id,
            "state": state,
            "progress": progress,
            "stage": stage,
            "error": None,
            "started_at": None,
            "finished_at": None,
        }
