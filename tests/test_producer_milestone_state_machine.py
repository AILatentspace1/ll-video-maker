from __future__ import annotations

from types import SimpleNamespace

from langchain.messages import AIMessage

from ll_video_maker.producer import _derive_milestone_state_updates


def test_research_completion_advances_to_script() -> None:
    state = SimpleNamespace(
        current_milestone="research",
        milestone_research="pending",
        milestone_script="pending",
    )

    updates = _derive_milestone_state_updates(
        agent_name="researcher",
        description="do research",
        result={
            "research_file": "output/research.md",
            "messages": [AIMessage(content="ok")],
        },
        state=state,
    )

    assert updates["milestone_research"] == "completed"
    assert updates["milestone_script"] == "in_progress"
    assert updates["current_milestone"] == "script"


def test_scriptwriter_completion_keeps_script_in_progress() -> None:
    state = SimpleNamespace(
        current_milestone="script",
        milestone_research="completed",
        milestone_script="pending",
    )

    updates = _derive_milestone_state_updates(
        agent_name="scriptwriter",
        description="write script",
        result={
            "script_plan_file": "output/script-plan.json",
            "script_file": "output/script.md",
            "contract_file": "output/script-contract.json",
            "messages": [AIMessage(content="ok")],
        },
        state=state,
    )

    assert updates["milestone_research"] == "completed"
    assert updates["milestone_script"] == "in_progress"
    assert updates["current_milestone"] == "script"


def test_eval_pass_marks_pipeline_done() -> None:
    state = SimpleNamespace(
        current_milestone="script",
        milestone_research="completed",
        milestone_script="in_progress",
    )

    updates = _derive_milestone_state_updates(
        agent_name="evaluator",
        description="milestone: script\nphase: eval",
        result={
            "script_eval_file": "output/script-eval.json",
            "messages": [AIMessage(content='{"pass": true, "weighted_total": 82.5}')],
        },
        state=state,
    )

    assert updates["milestone_research"] == "completed"
    assert updates["milestone_script"] == "completed"
    assert updates["current_milestone"] == "done"


def test_eval_fail_keeps_pipeline_in_script() -> None:
    state = SimpleNamespace(
        current_milestone="script",
        milestone_research="completed",
        milestone_script="in_progress",
    )

    updates = _derive_milestone_state_updates(
        agent_name="evaluator",
        description="milestone: script\nphase: eval",
        result={
            "script_eval_file": "output/script-eval.json",
            "messages": [AIMessage(content='{"pass": false, "weighted_total": 70.0}')],
        },
        state=state,
    )

    assert updates["milestone_script"] == "in_progress"
    assert updates["current_milestone"] == "script"


def test_research_eval_does_not_force_script_milestone() -> None:
    state = SimpleNamespace(
        current_milestone="research",
        milestone_research="in_progress",
        milestone_script="pending",
    )

    updates = _derive_milestone_state_updates(
        agent_name="evaluator",
        description="milestone: research\nphase: eval",
        result={
            "messages": [AIMessage(content='{"pass": true, "weighted_total": 88.0}')],
        },
        state=state,
    )

    assert updates["milestone_research"] == "completed"
    assert updates["milestone_script"] == "pending"
    assert updates["current_milestone"] == "research"
