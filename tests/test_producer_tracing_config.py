from __future__ import annotations

from uuid import UUID

from ll_video_maker.producer import _child_config, _root_langsmith_extra


def test_child_config_does_not_reuse_root_run_id_or_thread_config() -> None:
    root_run_id = UUID("00000000-0000-0000-0000-000000000123")
    base = {
        "run_id": root_run_id,
        "configurable": {"thread_id": "video-thread"},
        "metadata": {"topic": "AI Agent", "eval_mode": "gan"},
        "tags": ["pipeline:video-maker", "eval_mode:gan"],
        "recursion_limit": 50,
    }

    child = _child_config(
        base,
        agent_name="evaluator",
        description="milestone: script\nphase: eval",
    )

    assert "run_id" not in child
    assert "configurable" not in child
    assert child["metadata"]["pipeline_run_id"] == str(root_run_id)
    assert child["metadata"]["thread_id"] == "video-thread"
    assert child["metadata"]["agent_name"] == "evaluator"
    assert child["metadata"]["milestone"] == "script"
    assert child["metadata"]["phase"] == "eval"
    assert "agent:evaluator" in child["tags"]
    assert "milestone:script" in child["tags"]
    assert "phase:eval" in child["tags"]


def test_root_langsmith_extra_uses_pipeline_run_id_and_thread_id() -> None:
    root_run_id = UUID("00000000-0000-0000-0000-000000000456")
    extra = _root_langsmith_extra({
        "run_id": root_run_id,
        "configurable": {"thread_id": "video-thread"},
        "metadata": {"topic": "AI Agent"},
        "tags": ["pipeline:video-maker"],
    })

    assert extra["run_id"] == root_run_id
    assert extra["metadata"]["pipeline_run_id"] == str(root_run_id)
    assert extra["metadata"]["thread_id"] == "video-thread"
    assert extra["metadata"]["topic"] == "AI Agent"
