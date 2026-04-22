from __future__ import annotations

import json

from ll_video_maker.validators import validate_script_artifacts


def test_validate_script_artifacts_pass(tmp_path):
    out = tmp_path
    (out / "script-contract.json").write_text(json.dumps({
        "target_scene_count": {"min": 2, "max": 4},
        "target_duration_frames": {"min": 60, "max": 600},
        "narrative_structure": {"opening_type": "hook", "closing_type": "cta"},
        "key_topics": [
            {"topic": "market surge", "narrative_role": "hook"},
            {"topic": "call to action", "narrative_role": "cta"},
        ],
    }), encoding="utf-8")
    (out / "script-plan.json").write_text(json.dumps({
        "target_audience": "technical",
        "opening_type": "hook",
        "closing_type": "cta",
        "total_duration_estimate": 4,
        "chapters": [],
        "scenes": [
            {"scene_number": 1, "title": "Intro", "type": "narration", "contract_topic": "market surge", "narrative_role": "hook", "duration_estimate": 2, "purpose": "open", "needs": []},
            {"scene_number": 2, "title": "CTA", "type": "narration", "contract_topic": "call to action", "narrative_role": "cta", "duration_estimate": 2, "purpose": "close", "needs": []},
        ],
    }), encoding="utf-8")
    script = """## Scene 1: Intro
type: narration
contract_topic: "market surge"
narrative_role: hook
duration_estimate: 2

## Scene 2: CTA
type: narration
contract_topic: "call to action"
narrative_role: cta
duration_estimate: 2
"""
    (out / "script.md").write_text(script, encoding="utf-8")

    result = validate_script_artifacts(str(out))
    assert result["plan"] == []
    assert result["contract"] == []
    assert result["consistency"] == []
    assert result["all"] == []
