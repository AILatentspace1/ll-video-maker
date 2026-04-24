from __future__ import annotations

import json

from ll_video_maker.validators import run_evaluator_precheck


def test_contract_review_precheck_fails_fast_on_missing_file(tmp_path) -> None:
    result = run_evaluator_precheck(str(tmp_path), milestone="script", phase="contract_review")
    assert result is not None
    assert result["pass"] is False
    assert result["phase"] == "contract_review"


def test_contract_review_precheck_rejects_noncanonical_key_topic_roles(tmp_path) -> None:
    (tmp_path / "script-contract.json").write_text(json.dumps({
        "version": 1,
        "target_scene_count": {"min": 2, "max": 4},
        "target_duration_frames": {"min": 60, "max": 600},
        "narrative_structure": {"opening_type": "hook", "closing_type": "CTA"},
        "audience": "technical",
        "key_topics": [
            {"topic": "AI Agent 技术原理", "narrative_role": "技术原理"},
            {"topic": "行动建议", "narrative_role": "CTA"},
        ],
        "constraints": {"max_consecutive_same_type": 3},
    }), encoding="utf-8")

    result = run_evaluator_precheck(str(tmp_path), milestone="script", phase="contract_review")

    assert result is not None
    assert result["pass"] is False
    fields = {issue["field"] for issue in result["issues"]}
    assert "narrative_structure.closing_type" in fields
    assert "key_topics[0].narrative_role" in fields
    assert "key_topics[1].narrative_role" in fields


def test_contract_review_precheck_accepts_canonical_contract(tmp_path) -> None:
    (tmp_path / "script-contract.json").write_text(json.dumps({
        "version": 1,
        "target_scene_count": {"min": 2, "max": 4},
        "target_duration_frames": {"min": 60, "max": 600},
        "narrative_structure": {"opening_type": "hook", "closing_type": "cta"},
        "audience": "technical",
        "key_topics": [
            {"topic": "AI Agent 技术原理", "narrative_role": "hook"},
            {"topic": "行动建议", "narrative_role": "cta"},
        ],
        "constraints": {"max_consecutive_same_type": 3},
    }), encoding="utf-8")

    assert run_evaluator_precheck(str(tmp_path), milestone="script", phase="contract_review") is None


def test_script_eval_precheck_returns_none_when_valid(tmp_path) -> None:
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

    result = run_evaluator_precheck(str(out), milestone="script", phase="eval")
    assert result is None


def test_script_eval_precheck_fails_fast_on_invalid_plan(tmp_path) -> None:
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
    (out / "script-plan.json").write_text(json.dumps({
        "target_audience": "technical",
        "opening_type": "hook",
        "closing_type": "cta",
        "total_duration_estimate": 4,
        "chapters": [],
        "scenes": [
            {"scene_number": 2, "title": "Broken", "type": "narration", "contract_topic": "market surge", "narrative_role": "hook", "duration_estimate": 2, "purpose": "open", "needs": []},
        ],
    }), encoding="utf-8")
    (out / "script.md").write_text("", encoding="utf-8")

    result = run_evaluator_precheck(str(out), milestone="script", phase="eval")
    assert result is not None
    assert result["pass"] is False
    assert result["phase"] == "eval"
    assert result["iteration_fixes"]
