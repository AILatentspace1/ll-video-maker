from __future__ import annotations

import json
from types import SimpleNamespace

from ll_video_maker.producer import _maybe_short_circuit_evaluator


def test_maybe_short_circuit_evaluator_writes_eval_result(tmp_path) -> None:
    out = tmp_path
    (out / "script-contract.json").write_text(json.dumps({
        "version": 1,
        "target_scene_count": {"min": 2, "max": 4},
        "target_duration_frames": {"min": 60, "max": 600},
        "narrative_structure": {"opening_type": "hook", "closing_type": "cta"},
        "audience": "technical",
        "key_topics": [
            {"topic": "market surge", "narrative_role": "hook"},
            {"topic": "call to action", "narrative_role": "cta"},
        ],
        "constraints": {"max_consecutive_same_type": 3},
    }), encoding="utf-8")
    (out / "script-plan.json").write_text('{"scenes": []}', encoding="utf-8")
    (out / "script.md").write_text("", encoding="utf-8")

    state = SimpleNamespace(output_dir=str(out), current_milestone="script")
    result = _maybe_short_circuit_evaluator(
        "evaluator",
        "milestone: script\nphase: eval",
        state,
    )

    assert result is not None
    assert "script_eval_file" in result
    assert (out / "script-eval.json").exists()
