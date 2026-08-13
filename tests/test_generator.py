from pathlib import Path

from soundslo.config import Settings
from soundslo.generator import GenerationRunner, progress_from_line


def test_progress_parser() -> None:
    assert progress_from_line("[1/5] T5Gemma encode")[0] == 18
    assert progress_from_line("sampling step 4/8")[0] == 52.5
    assert progress_from_line("[5/5] Unpatch + write WAV")[0] == 95
    assert progress_from_line("unrelated output") is None


def test_medium_command_is_reproducible(tmp_path: Path) -> None:
    settings = Settings(
        root=tmp_path,
        data_dir=tmp_path / "data",
        database_path=tmp_path / "data" / "db.sqlite3",
        generations_dir=tmp_path / "data" / "generations",
        sa3_root=tmp_path / "stable-audio-3",
        static_dir=tmp_path / "static",
    )
    runner = GenerationRunner(settings)
    command = runner.command_for(
        {
            "prompt": "cinematic instrumental",
            "negative_prompt": "vocals",
            "duration_seconds": 60,
            "steps": 8,
            "seed": 42,
            "cfg_scale": 3.0,
        },
        tmp_path / "out.wav",
    )
    assert command[0] == str(settings.sa3_executable)
    assert command[command.index("--dit") + 1] == "medium"
    assert command[command.index("--decoder") + 1] == "same-l"
    assert command[command.index("--seed") + 1] == "42"
    assert command[command.index("--out") + 1] == str(tmp_path / "out.wav")
