from __future__ import annotations

from pathlib import Path

from ll_video_maker.prompts import load_prompt


def test_scriptwriter_prompt_is_clean_utf8_text():
    prompt = load_prompt("scriptwriter")
    assert "????" not in prompt
    assert "\ufffd" not in prompt
    assert "Pass 1: Write `script-plan.json`" in prompt
    assert "Pass 2: Write `script.md`" in prompt
    assert "type:" in prompt
    assert "contract_topic:" in prompt
    assert "narrative_role:" in prompt


def test_scriptwriter_prompt_file_round_trips_as_utf8():
    path = Path("src/ll_video_maker/prompts/scriptwriter.md")
    text = path.read_text(encoding="utf-8")
    data = path.read_bytes()
    assert data.startswith(b"# Role: Video Scriptwriter")
    assert text.startswith("# Role: Video Scriptwriter")
