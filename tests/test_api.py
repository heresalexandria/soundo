from pathlib import Path

from fastapi.testclient import TestClient

from soundslo.app import create_app
from soundslo.config import Settings


def test_generation_crud_and_audio(tmp_path: Path) -> None:
    root = tmp_path
    static_dir = Path(__file__).parents[1] / "soundslo" / "static"
    settings = Settings(
        root=root,
        data_dir=root / "data",
        database_path=root / "data" / "soundslo.sqlite3",
        generations_dir=root / "data" / "generations",
        sa3_root=root / ".runtime" / "stable-audio-3",
        static_dir=static_dir,
    )
    app = create_app(settings, start_jobs=False)

    with TestClient(app) as client:
        created = client.post(
            "/api/generations",
            json={
                "prompt": "Dark analog synth instrumental",
                "duration_seconds": 30,
                "seed": 123,
            },
        )
        assert created.status_code == 202
        generation = created.json()
        generation_id = generation["id"]
        assert generation["status"] == "queued"
        assert generation["seed"] == 123
        assert "vocals" in generation["negative_prompt"]

        renamed = client.patch(f"/api/generations/{generation_id}", json={"name": "Night Drive"})
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "Night Drive"

        output_path = settings.generations_dir / f"{generation_id}.wav"
        output_path.write_bytes(b"RIFF-test-wave")
        app.state.database.update(
            generation_id,
            status="completed",
            progress=100,
            stage="Ready",
            file_path=str(output_path),
            file_size=output_path.stat().st_size,
        )

        audio = client.get(f"/api/generations/{generation_id}/audio")
        assert audio.status_code == 200
        assert audio.content == b"RIFF-test-wave"

        download = client.get(f"/api/generations/{generation_id}/download")
        assert download.status_code == 200
        assert "Night%20Drive.wav" in download.headers["content-disposition"]

        deleted = client.delete(f"/api/generations/{generation_id}")
        assert deleted.status_code == 204
        assert not output_path.exists()
        assert client.get(f"/api/generations/{generation_id}").status_code == 404


def test_rejects_delete_while_running(tmp_path: Path) -> None:
    static_dir = Path(__file__).parents[1] / "soundslo" / "static"
    settings = Settings(
        root=tmp_path,
        data_dir=tmp_path / "data",
        database_path=tmp_path / "data" / "soundslo.sqlite3",
        generations_dir=tmp_path / "data" / "generations",
        sa3_root=tmp_path / ".runtime",
        static_dir=static_dir,
    )
    app = create_app(settings, start_jobs=False)
    with TestClient(app) as client:
        generation = client.post(
            "/api/generations", json={"prompt": "Orchestral instrumental score"}
        ).json()
        app.state.database.update(generation["id"], status="running")
        response = client.delete(f"/api/generations/{generation['id']}")
        assert response.status_code == 409
