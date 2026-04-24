from __future__ import annotations

import json

from ll_video_maker.validators.script_contract import check_script_contract
from ll_video_maker.validators.script_plan import check_script_plan


def test_validators_do_not_crash_on_string_key_topics(tmp_path) -> None:
    out = tmp_path
    (out / "script-contract.json").write_text(json.dumps({
        "version": 1,
        "target_scene_count": {"min": 1, "max": 3},
        "target_duration_frames": {"min": 30, "max": 300},
        "narrative_structure": {"opening_type": "hook", "closing_type": "cta"},
        "audience": "general",
        "key_topics": ["market surge", "call to action"],
        "constraints": {"max_consecutive_same_type": 3},
    }), encoding="utf-8")
    (out / "script-plan.json").write_text(json.dumps({
        "total_duration_estimate": 4,
        "scenes": [
            {"scene_number": 1, "type": "narration", "contract_topic": "market surge", "narrative_role": "hook", "duration_estimate": 2},
            {"scene_number": 2, "type": "narration", "contract_topic": "call to action", "narrative_role": "cta", "duration_estimate": 2},
        ],
    }), encoding="utf-8")
    (out / "script.md").write_text("""## Scene 1: Intro
type: narration
contract_topic: "market surge"
narrative_role: hook
duration_estimate: 2

## Scene 2: CTA
type: narration
contract_topic: "call to action"
narrative_role: cta
duration_estimate: 2
""", encoding="utf-8")

    assert isinstance(check_script_plan(str(out)), list)
    assert isinstance(check_script_contract(str(out)), list)
