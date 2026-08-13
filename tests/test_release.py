from pathlib import Path

from soundslo.config import SA3_REVISION, SA3_WEIGHTS_REVISION

ROOT = Path(__file__).parents[1]


def test_release_contains_required_license_and_notice_files() -> None:
    required = (
        ROOT / "LICENSE",
        ROOT / "NOTICE",
        ROOT / "licenses" / "STABILITY_AI_COMMUNITY_LICENSE.md",
        ROOT / "licenses" / "GEMMA_TERMS_OF_USE.md",
    )
    assert all(path.is_file() and path.stat().st_size > 0 for path in required)

    notice = (ROOT / "NOTICE").read_text()
    assert "This Stability AI Model is licensed under" in notice
    assert "Gemma is provided under and subject to" in notice


def test_third_party_revisions_and_ui_attribution_are_pinned() -> None:
    assert len(SA3_REVISION) == 40
    assert len(SA3_WEIGHTS_REVISION) == 40
    assert "Powered by Stability AI" in (ROOT / "soundslo" / "static" / "index.html").read_text()
