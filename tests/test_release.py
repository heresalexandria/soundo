from pathlib import Path

from soundslo.config import SA3_REVISION, SA3_WEIGHTS_REVISION

ROOT = Path(__file__).parents[1]


def test_release_contains_required_license_and_notice_files() -> None:
    required = (
        ROOT / "LICENSE",
        ROOT / "NOTICE",
        ROOT / "docs" / "assets" / "soundslo-app.jpg",
        ROOT / "licenses" / "STABILITY_AI_COMMUNITY_LICENSE.md",
        ROOT / "licenses" / "GEMMA_TERMS_OF_USE.md",
        ROOT / "soundslo" / "static" / "soundslo-icon.svg",
    )
    assert all(path.is_file() and path.stat().st_size > 0 for path in required)

    notice = (ROOT / "NOTICE").read_text()
    assert "This Stability AI Model is licensed under" in notice
    assert "Gemma is provided under and subject to" in notice


def test_third_party_revisions_and_ui_attribution_are_pinned() -> None:
    assert len(SA3_REVISION) == 40
    assert len(SA3_WEIGHTS_REVISION) == 40
    assert "Powered by Stability AI" in (ROOT / "soundslo" / "static" / "index.html").read_text()


def test_readme_starts_with_branding_and_has_a_one_command_setup() -> None:
    readme = (ROOT / "README.md").read_text()
    assert readme.startswith('<div align="center">')
    assert 'src="soundslo/static/soundslo-icon.svg"' in readme
    assert "<p><em>Generate private," in readme
    assert 'src="docs/assets/soundslo-app.jpg"' in readme
    assert "bash scripts/setup.sh && bash scripts/run.sh" in readme
