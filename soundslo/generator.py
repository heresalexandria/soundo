from __future__ import annotations

import os
import pty
import queue
import re
import select
import signal
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path

from soundslo.config import Settings
from soundslo.database import Database

ANSI_RE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
STEP_RE = re.compile(r"step\s+(\d+)\s*/\s*(\d+)", re.IGNORECASE)
MAX_LOG_CHARS = 40_000


class GenerationRunner:
    def __init__(self, settings: Settings):
        self.settings = settings

    def is_ready(self) -> bool:
        return self.settings.sa3_executable.is_file() and self.settings.runtime_python.is_file()

    def command_for(self, generation: dict, output_path: Path) -> list[str]:
        command = [
            str(self.settings.sa3_executable),
            "--prompt",
            generation["prompt"],
            "--negative-prompt",
            generation["negative_prompt"],
            "--dit",
            "medium",
            "--decoder",
            "same-l",
            "--dit-dtype",
            "fp16",
            "--seconds",
            str(generation["duration_seconds"]),
            "--steps",
            str(generation["steps"]),
            "--seed",
            str(generation["seed"]),
            "--cfg",
            str(generation["cfg_scale"]),
            "--apg",
            "1.0",
            "--out",
            str(output_path),
        ]
        return command

    def run(
        self,
        generation: dict,
        output_path: Path,
        on_output: Callable[[str], None],
        on_progress: Callable[[float, str], None],
        on_process: Callable[[subprocess.Popen[bytes] | None], None],
    ) -> tuple[int, str]:
        if not self.is_ready():
            return 127, "Stable Audio 3 is not installed. Run ./scripts/setup.sh first."

        master_fd, slave_fd = pty.openpty()
        process: subprocess.Popen[bytes] | None = None
        captured: list[str] = []
        pending = ""
        try:
            process = subprocess.Popen(
                self.command_for(generation, output_path),
                cwd=self.settings.mlx_root,
                stdin=subprocess.DEVNULL,
                stdout=slave_fd,
                stderr=slave_fd,
                start_new_session=True,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            on_process(process)
            os.close(slave_fd)
            slave_fd = -1

            while True:
                readable, _, _ = select.select([master_fd], [], [], 0.25)
                if readable:
                    try:
                        chunk = os.read(master_fd, 8192).decode("utf-8", errors="replace")
                    except OSError:
                        chunk = ""
                    if chunk:
                        clean = ANSI_RE.sub("", chunk).replace("\r", "\n")
                        captured.append(clean)
                        pending += clean
                        lines = pending.split("\n")
                        pending = lines.pop()
                        for line in lines:
                            stripped = line.strip()
                            if stripped:
                                on_output(stripped)
                                progress = progress_from_line(stripped)
                                if progress:
                                    on_progress(*progress)
                if process.poll() is not None:
                    while True:
                        try:
                            tail = os.read(master_fd, 8192)
                        except OSError:
                            break
                        if not tail:
                            break
                        captured.append(ANSI_RE.sub("", tail.decode("utf-8", errors="replace")))
                    break
            if pending.strip():
                on_output(pending.strip())
            return process.returncode or 0, "".join(captured)[-MAX_LOG_CHARS:]
        finally:
            on_process(None)
            if slave_fd >= 0:
                os.close(slave_fd)
            os.close(master_fd)


def progress_from_line(line: str) -> tuple[float, str] | None:
    step_match = STEP_RE.search(line)
    if step_match:
        current, total = map(int, step_match.groups())
        return 35 + (current / max(total, 1)) * 35, f"Sampling — step {current} of {total}"
    markers = (
        ("downloading", 3, "Downloading model weights"),
        ("SA3 → MLX", 8, "Starting Stable Audio 3"),
        ("[1/5]", 18, "Encoding the prompt"),
        ("[2/5]", 28, "Building conditioning"),
        ("[3/5]", 35, "Loading and sampling the music model"),
        ("[4/5]", 78, "Decoding audio"),
        ("[5/5]", 95, "Writing the WAV file"),
        ("saved", 99, "Finalizing"),
    )
    lowered = line.lower()
    for marker, progress, stage in markers:
        if marker.lower() in lowered:
            return float(progress), stage
    return None


class JobManager:
    def __init__(
        self,
        database: Database,
        settings: Settings,
        runner: GenerationRunner | None = None,
    ):
        self.database = database
        self.settings = settings
        self.runner = runner or GenerationRunner(settings)
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._current_id: str | None = None
        self._current_process: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._worker, name="soundslo-generator", daemon=True)
        self._thread.start()
        for generation_id in self.database.queued_ids():
            self._queue.put(generation_id)

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            process = self._current_process
            generation_id = self._current_id
        if process and process.poll() is None:
            _terminate_process(process)
        if generation_id:
            self.database.update(
                generation_id,
                status="failed",
                stage="Interrupted",
                error="Soundslo stopped before this generation finished.",
            )
        self._queue.put(None)
        if self._thread:
            self._thread.join(timeout=3)

    def submit(self, generation_id: str) -> None:
        self._queue.put(generation_id)

    def cancel(self, generation_id: str) -> bool:
        generation = self.database.get(generation_id)
        if generation is None or generation["status"] not in {"queued", "running"}:
            return False
        self.database.update(
            generation_id,
            status="cancelled",
            stage="Cancelled",
            error="Cancelled by user.",
        )
        with self._lock:
            if self._current_id == generation_id and self._current_process:
                _terminate_process(self._current_process)
        return True

    def _worker(self) -> None:
        while not self._stop.is_set():
            generation_id = self._queue.get()
            if generation_id is None:
                break
            generation = self.database.get(generation_id)
            if generation is None or generation["status"] != "queued":
                continue
            self._run_one(generation)

    def _run_one(self, generation: dict) -> None:
        generation_id = generation["id"]
        output_path = self.settings.generations_dir / f"{generation_id}.wav"
        started = time.monotonic()
        log_lines: list[str] = []
        last_persist = [0.0]

        with self._lock:
            self._current_id = generation_id
        self.database.update(
            generation_id,
            status="running",
            progress=1.0,
            stage="Starting the local model",
            error=None,
        )

        def on_output(line: str) -> None:
            log_lines.append(line)
            if sum(map(len, log_lines)) > MAX_LOG_CHARS:
                del log_lines[: max(1, len(log_lines) // 4)]

        def on_progress(progress: float, stage: str) -> None:
            now = time.monotonic()
            if now - last_persist[0] >= 0.15 or progress >= 95:
                self.database.update(generation_id, progress=progress, stage=stage)
                last_persist[0] = now

        def on_process(process: subprocess.Popen[bytes] | None) -> None:
            with self._lock:
                self._current_process = process

        try:
            return_code, raw_log = self.runner.run(
                generation, output_path, on_output, on_progress, on_process
            )
            elapsed = time.monotonic() - started
            current = self.database.get(generation_id)
            if current and current["status"] == "cancelled":
                output_path.unlink(missing_ok=True)
                self.database.update(generation_id, elapsed_seconds=elapsed, log=raw_log)
            elif return_code == 0 and output_path.is_file():
                self.database.update(
                    generation_id,
                    status="completed",
                    progress=100.0,
                    stage="Ready",
                    file_path=str(output_path),
                    file_size=output_path.stat().st_size,
                    elapsed_seconds=elapsed,
                    error=None,
                    log=raw_log,
                )
            else:
                message = _last_useful_line(raw_log or "\n".join(log_lines))
                self.database.update(
                    generation_id,
                    status="failed",
                    stage="Generation failed",
                    error=message or f"Stable Audio 3 exited with code {return_code}.",
                    elapsed_seconds=elapsed,
                    log=raw_log,
                )
                output_path.unlink(missing_ok=True)
        except Exception as error:
            output_path.unlink(missing_ok=True)
            self.database.update(
                generation_id,
                status="failed",
                stage="Generation failed",
                error=str(error),
                elapsed_seconds=time.monotonic() - started,
                log="\n".join(log_lines)[-MAX_LOG_CHARS:],
            )
        finally:
            with self._lock:
                self._current_id = None
                self._current_process = None


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=3)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def _last_useful_line(log: str) -> str:
    lines = [line.strip() for line in log.replace("\r", "\n").splitlines() if line.strip()]
    for line in reversed(lines):
        if "error" in line.lower() or "traceback" in line.lower():
            return line[-1000:]
    return lines[-1][-1000:] if lines else ""
