from __future__ import annotations

import re
import secrets
import shutil
import subprocess
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from soundslo import __version__
from soundslo.config import SA3_REVISION, SA3_WEIGHTS_REVISION, Settings
from soundslo.database import TERMINAL_STATUSES, Database
from soundslo.generator import GenerationRunner, JobManager

DEFAULT_NEGATIVE_PROMPT = "vocals, singing, speech, spoken word, lyrics, choir"
REQUIRED_WEIGHTS = (
    "models/mlx/t5gemma_f16.npz",
    "models/mlx/dit_medium_f16.npz",
    "models/mlx/same_l_decoder_f32.npz",
)


class GenerationCreate(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    name: str | None = Field(default=None, max_length=120)
    negative_prompt: str = Field(default=DEFAULT_NEGATIVE_PROMPT, max_length=1000)
    duration_seconds: float = Field(default=30, ge=5, le=380)
    seed: int | None = Field(default=None, ge=0, le=2**32 - 1)
    steps: int = Field(default=8, ge=1, le=32)
    cfg_scale: float = Field(default=3.0, ge=1, le=10)

    @field_validator("prompt", "negative_prompt")
    @classmethod
    def strip_prompt(cls, value: str) -> str:
        return value.strip()

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None


class GenerationRename(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


def create_app(settings: Settings | None = None, *, start_jobs: bool = True) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.ensure_directories()
    database = Database(settings.database_path)
    database.initialize()
    database.fail_interrupted()
    runner = GenerationRunner(settings)
    jobs = JobManager(database, settings, runner)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if start_jobs:
            jobs.start()
        yield
        if start_jobs:
            jobs.stop()

    app = FastAPI(title="Soundslo", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.database = database
    app.state.jobs = jobs

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/system")
    def system_status() -> dict:
        usage = shutil.disk_usage(settings.root)
        weights = {
            Path(relative).name: (settings.mlx_root / relative).exists()
            for relative in REQUIRED_WEIGHTS
        }
        return {
            "app_version": __version__,
            "model": "Stable Audio 3 Medium",
            "model_revision": SA3_WEIGHTS_REVISION[:12],
            "runtime_revision": SA3_REVISION[:12],
            "runtime_installed": runner.is_ready(),
            "weights_ready": all(weights.values()),
            "weights": weights,
            "ready": runner.is_ready() and all(weights.values()),
            "free_disk_bytes": usage.free,
            "data_directory": str(settings.data_dir),
        }

    @app.get("/api/generations")
    def list_generations(limit: Annotated[int, Query(ge=1, le=500)] = 100) -> list[dict]:
        return database.list(limit=limit)

    @app.post("/api/generations", status_code=202)
    def create_generation(payload: GenerationCreate) -> dict:
        generation_id = str(uuid.uuid4())
        seed = payload.seed if payload.seed is not None else secrets.randbelow(2**32)
        name = payload.name or suggested_name(payload.prompt)
        generation = database.create(
            {
                "id": generation_id,
                "name": name,
                "prompt": payload.prompt,
                "negative_prompt": payload.negative_prompt,
                "duration_seconds": payload.duration_seconds,
                "seed": seed,
                "steps": payload.steps,
                "cfg_scale": payload.cfg_scale,
                "model_revision": SA3_WEIGHTS_REVISION,
            }
        )
        jobs.submit(generation_id)
        return generation

    @app.get("/api/generations/{generation_id}")
    def get_generation(generation_id: str) -> dict:
        return require_generation(database, generation_id)

    @app.patch("/api/generations/{generation_id}")
    def rename_generation(generation_id: str, payload: GenerationRename) -> dict:
        require_generation(database, generation_id)
        updated = database.update(generation_id, name=payload.name)
        assert updated is not None
        return updated

    @app.post("/api/generations/{generation_id}/retry", status_code=202)
    def retry_generation(generation_id: str) -> dict:
        original = require_generation(database, generation_id)
        payload = GenerationCreate(
            prompt=original["prompt"],
            name=f"{original['name']} — retry",
            negative_prompt=original["negative_prompt"],
            duration_seconds=original["duration_seconds"],
            seed=original["seed"],
            steps=original["steps"],
            cfg_scale=original["cfg_scale"],
        )
        return create_generation(payload)

    @app.post("/api/generations/{generation_id}/cancel")
    def cancel_generation(generation_id: str) -> dict:
        generation = require_generation(database, generation_id)
        if generation["status"] in TERMINAL_STATUSES:
            raise HTTPException(status_code=409, detail="This generation is no longer active.")
        jobs.cancel(generation_id)
        return require_generation(database, generation_id)

    @app.delete("/api/generations/{generation_id}", status_code=204)
    def delete_generation(generation_id: str) -> Response:
        generation = require_generation(database, generation_id)
        if generation["status"] == "running":
            raise HTTPException(
                status_code=409, detail="Cancel this generation before deleting it."
            )
        deleted = database.delete(generation_id)
        if deleted and deleted.get("file_path"):
            safe_audio_path(settings, deleted).unlink(missing_ok=True)
        return Response(status_code=204)

    @app.get("/api/generations/{generation_id}/audio")
    def play_audio(generation_id: str) -> FileResponse:
        generation = require_generation(database, generation_id)
        path = require_audio_path(settings, generation)
        return FileResponse(path, media_type="audio/wav")

    @app.get("/api/generations/{generation_id}/download")
    def download_audio(generation_id: str) -> FileResponse:
        generation = require_generation(database, generation_id)
        path = require_audio_path(settings, generation)
        return FileResponse(
            path,
            media_type="audio/wav",
            filename=f"{safe_filename(generation['name'])}.wav",
        )

    @app.post("/api/generations/{generation_id}/reveal")
    def reveal_audio(generation_id: str) -> dict[str, bool]:
        generation = require_generation(database, generation_id)
        path = require_audio_path(settings, generation)
        result = subprocess.run(["open", "-R", str(path)], check=False)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail="Finder could not reveal this file.")
        return {"revealed": True}

    @app.get("/api/generations/{generation_id}/log")
    def generation_log(generation_id: str) -> dict[str, str]:
        generation = require_generation(database, generation_id)
        return {"log": generation.get("log") or "No runtime log yet."}

    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(request: Request, path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        return FileResponse(settings.static_dir / "index.html")

    return app


def require_generation(database: Database, generation_id: str) -> dict:
    generation = database.get(generation_id)
    if generation is None:
        raise HTTPException(status_code=404, detail="Generation not found.")
    return generation


def safe_audio_path(settings: Settings, generation: dict) -> Path:
    raw_path = generation.get("file_path")
    default_path = settings.generations_dir / f"{generation['id']}.wav"
    path = Path(raw_path).resolve() if raw_path else default_path
    root = settings.generations_dir.resolve()
    if not path.is_relative_to(root):
        raise HTTPException(status_code=400, detail="Invalid audio path.")
    return path


def require_audio_path(settings: Settings, generation: dict) -> Path:
    path = safe_audio_path(settings, generation)
    if generation["status"] != "completed" or not path.is_file():
        raise HTTPException(status_code=404, detail="Audio is not available yet.")
    return path


def suggested_name(prompt: str) -> str:
    words = re.sub(r"\s+", " ", prompt).strip()
    return words[:64].rstrip(" ,.;:-") or "Untitled generation"


def safe_filename(name: str) -> str:
    filename = re.sub(r"[^\w\-. ]+", "", name, flags=re.UNICODE).strip(" .")
    return filename[:100] or "soundslo-generation"


app = create_app()
