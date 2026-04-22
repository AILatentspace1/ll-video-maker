from __future__ import annotations

import json

from ll_video_maker.validators import check_script_plan


def test_check_script_plan_pass(tmp_path):
    out = tmp_path
    (out / "script-contract.json").write_text(json.dumps({
        "target_scene_count": {"min": 3, "max": 5},
        "target_duration_frames": {"min": 300, "max": 600},
        "narrative_structure": {"opening_type": "hook", "closing_type": "cta"},
        "key_topics": [
            {"topic": "market surge", "narrative_role": "hook"},
            {"topic": "competition", "narrative_role": "climax"},
            {"topic": "call to action", "narrative_role": "cta"},
        ],
    }), encoding="utf-8")
    plan = """## Scene Plan 1: Intro
type: narration
contract_topic: "market surge"
narrative_role: hook
duration_estimate: 4

## Scene Plan 2: Competition
type: data_card
contract_topic: "competition"
narrative_role: climax
duration_estimate: 5

## Scene Plan 3: CTA
type: narration
contract_topic: "call to action"
narrative_role: cta
duration_estimate: 4
"""
    (out / "script-plan.md").write_text(plan, encoding="utf-8")
    assert check_script_plan(str(out)) == []
