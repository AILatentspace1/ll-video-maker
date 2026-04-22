from __future__ import annotations

from ll_video_maker.validators import check_script_plan_consistency


def test_check_script_plan_consistency_pass(tmp_path):
    out = tmp_path
    (out / "script-plan.md").write_text("""## Scene Plan 1: Intro
type: narration
contract_topic: "market surge"
narrative_role: hook
duration_estimate: 4

## Scene Plan 2: CTA
type: narration
contract_topic: "call to action"
narrative_role: cta
duration_estimate: 4
""", encoding="utf-8")
    (out / "script.md").write_text("""## Scene 1: Intro
type: narration
contract_topic: "market surge"
narrative_role: hook
duration_estimate: 4

## Scene 2: CTA
type: narration
contract_topic: "call to action"
narrative_role: cta
duration_estimate: 4
""", encoding="utf-8")
    assert check_script_plan_consistency(str(out)) == []
