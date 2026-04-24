from __future__ import annotations

from pathlib import Path

from ll_video_maker.prompts import load_prompt, render_prompt


def test_scriptwriter_prompt_is_clean_utf8_text():
    prompt = load_prompt("scriptwriter")
    assert "????" not in prompt
    assert "�" not in prompt
    assert "Pass 1: Write `script-plan.json`" in prompt
    assert "Pass 2: Write `script.md`" in prompt
    assert "type:" in prompt
    assert "contract_topic:" in prompt
    assert "narrative_role:" in prompt
    assert "Data accuracy / source attribution" in prompt
    assert "No `data_card` contains unsupported numbers." in prompt


def test_scriptwriter_prompt_file_round_trips_as_utf8():
    path = Path("src/ll_video_maker/prompts/scriptwriter.md")
    text = path.read_text(encoding="utf-8")
    data = path.read_bytes()
    assert data.startswith(b"# Role: Video Scriptwriter")
    assert text.startswith("# Role: Video Scriptwriter")


def test_all_agent_prompts_live_in_markdown_files():
    prompt_dir = Path("src/ll_video_maker/prompts")
    expected = {"producer", "researcher", "scriptwriter", "evaluator"}
    actual = {path.stem for path in prompt_dir.glob("*.md")}
    assert expected.issubset(actual)


def test_render_prompt_without_template_variables_returns_markdown_verbatim():
    rendered = render_prompt("producer")
    assert rendered.startswith("# Role: Video Producer")
    assert "script-contract.json" in rendered
    assert "task(agent_name, description)" in rendered


def test_all_agent_prompt_files_are_clean_utf8_text():
    prompt_dir = Path("src/ll_video_maker/prompts")
    for path in prompt_dir.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert "锟" not in text
        assert "�" not in text
        assert "????" not in text
