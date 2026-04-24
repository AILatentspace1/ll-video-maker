from __future__ import annotations

from types import SimpleNamespace

from ll_video_maker.middleware.ratify_l1 import _build_failed_milestone_update


def test_research_ratify_failure_marks_research_failed() -> None:
    state = SimpleNamespace(
        milestone_script="pending",
        retry_research=1,
    )

    result = _build_failed_milestone_update(
        validation_target="research",
        tool_call_id="tool-1",
        feedback="- research.md 不存在",
        state=state,
    )

    updates = result.update
    assert updates["current_milestone"] == "research"
    assert updates["milestone_research"] == "failed"
    assert updates["milestone_script"] == "pending"
    assert updates["retry_research"] == 2
    assert updates["ratify_feedback"] == "- research.md 不存在"


def test_script_ratify_failure_marks_script_failed() -> None:
    state = SimpleNamespace(
        milestone_research="completed",
        retry_script=0,
    )

    result = _build_failed_milestone_update(
        validation_target="script",
        tool_call_id="tool-2",
        feedback="- script.md 不存在",
        state=state,
    )

    updates = result.update
    assert updates["current_milestone"] == "script"
    assert updates["milestone_research"] == "completed"
    assert updates["milestone_script"] == "failed"
    assert updates["retry_script"] == 1
    assert updates["ratify_feedback"] == "- script.md 不存在"
